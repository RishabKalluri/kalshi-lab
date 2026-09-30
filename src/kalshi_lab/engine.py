"""Event loop: feeds a time-ordered event stream to a strategy through an exchange (sim or live)."""

import logging
import time as _time

from .core.book import Book
from .core.portfolio import Portfolio
from .core.risk import RiskLimits
from .core.types import (BookDelta, BookSnapshot, FeedGap, Fill, MarketInfo, Side, SpotTick, Timer,
                         Trade)
from .strategy import Context, Strategy

log = logging.getLogger("engine")
NS = 1_000_000_000


class Engine:
    def __init__(self, strategy: Strategy, source, exchange, risk: RiskLimits | None = None,
                 timer_ms: int = 1000, has_book: bool = True, cash: float = 0.0,
                 spot_stale_s: float = 5, start_ts: int | None = None, timeline_s: float | None = None,
                 spot_map: dict[str, list[str]] | None = None, sizer=None):
        """`start_ts`: events before it only rebuild state (books, markets, spot); the strategy
        starts at the first event at/after it."""
        self.real_strategy = strategy
        self.strategy = _Idle()
        self.start_ts = start_ts
        self.source = source
        self.exchange = exchange
        self.timer_ns = timer_ms * 1_000_000
        self.has_book = has_book  # False: synthesize top of book from trades (backfill data)
        self.portfolio = Portfolio(cash)
        self.ctx = Context(exchange, risk or RiskLimits(), self.portfolio, spot_stale_s, spot_map, sizer)
        self.fills: list[Fill] = []
        self.settlements: list[tuple[int, str, float]] = []
        self.events = 0
        self._tops: dict[str, tuple] = {}
        # Periodic per-market snapshots (bid/ask/spot/strike + ctx.record values) for charts.
        self.timeline_ns = int(timeline_s * NS) if timeline_s else None
        self.timeline: list[dict] = []
        self._next_sample = 0

    # ------------------------------------------------------------------------
    def run(self):
        ctx = self.ctx
        next_timer = None
        wall = _time.time()
        started = False
        for ev in self.source:
            self.events += 1
            now = ev.ts
            if not started and (self.start_ts is None or now >= self.start_ts):
                ctx.now = now
                s = self.strategy = self.real_strategy
                s.on_start(ctx)
                for m in list(ctx.markets.values()):
                    if m.result is None:
                        s.on_market(ctx, m)
                started = True
                next_timer = now - now % self.timer_ns + self.timer_ns
            if next_timer is not None and now >= next_timer:
                if now - next_timer > 60 * NS:  # data gap: don't replay thousands of empty timers
                    next_timer = now - now % self.timer_ns
                while next_timer <= now:
                    self._advance(next_timer)
                    ctx.now = next_timer
                    s.on_timer(ctx)
                    self._check_loss()
                    if self.timeline_ns and next_timer >= self._next_sample:
                        self._sample(next_timer)
                        self._next_sample = next_timer + self.timeline_ns
                    next_timer += self.timer_ns
            self._advance(now)
            ctx.now = now
            self._dispatch(ev)
        if started:
            self.strategy.on_end(ctx)
        log.info("replayed %d events in %.1fs", self.events, _time.time() - wall)
        return self

    def _sample(self, t: int):
        ctx = self.ctx
        for m in ctx.active_markets():
            spot = ctx.spot(series=m.series)
            b = ctx.books.get(m.ticker)
            row = {"ts": t, "ticker": m.ticker, "bid": b.best_bid if b and b.valid else None,
                   "ask": b.best_ask if b and b.valid else None, "spot": spot, "strike": m.strike,
                   "pos": self.portfolio.pos.get(m.ticker, 0.0)}
            row.update(ctx.recorded.get(m.ticker, {}))
            self.timeline.append(row)

    def _advance(self, t: int):
        for f in self.exchange.process_until(t, self.ctx.books):
            self._on_fill(f)

    def _on_fill(self, f: Fill):
        self.portfolio.apply(f)
        self.fills.append(f)
        self.strategy.on_fill(self.ctx, f)
        self._check_loss()

    def _check_loss(self):
        lim = self.ctx.risk.max_loss
        if lim is not None and not self.ctx.halted and self.equity() < self.portfolio.start_cash - lim:
            log.warning("max_loss hit: halting and cancelling everything")
            self.ctx.halted = True
            self.ctx.cancel_all()

    def equity(self) -> float:
        marks = {t: b.mid for t, b in self.ctx.books.items() if b.mid is not None}
        return self.portfolio.equity(marks)

    def _dispatch(self, ev):
        ctx, s = self.ctx, self.strategy
        if isinstance(ev, BookDelta):
            book = ctx.books.get(ev.ticker)
            if book is None:
                return
            book.apply_delta(ev)
            self.exchange.on_delta(ev, book)
            self._maybe_on_book(ev.ticker, book)
        elif isinstance(ev, Trade):
            if not self.has_book:
                self._synth_book(ev)
            for f in self.exchange.on_trade(ev):
                self._on_fill(f)
            s.on_trade(ctx, ev)
        elif isinstance(ev, SpotTick):
            ctx._spot[ev.source] = (ev.ts, ev.price)
            s.on_spot(ctx, ev)
        elif isinstance(ev, BookSnapshot):
            book = ctx.books.setdefault(ev.ticker, Book(ev.ticker))
            book.apply_snapshot(ev)
            self.exchange.on_snapshot(ev.ticker)
            self._maybe_on_book(ev.ticker, book)
        elif isinstance(ev, MarketInfo):
            self._on_market(ev)
        elif isinstance(ev, FeedGap):
            if ev.stream.startswith("kalshi_ws/"):
                series = ev.stream.split("/")[1]
                for t, b in ctx.books.items():
                    if t.startswith(series):
                        b.valid = False
        elif isinstance(ev, Timer):
            pass  # clock tick from a live source

    def _on_market(self, m: MarketInfo):
        ctx = self.ctx
        known = ctx.markets.get(m.ticker)
        if known is not None and known.result is not None:
            return  # already settled
        if known is not None and known.strike is None and m.strike is not None:
            known.strike = m.strike
        if known is None:
            ctx.markets[m.ticker] = m
            ctx.books.setdefault(m.ticker, Book(m.ticker))
            if not self.has_book:
                ctx.books[m.ticker].valid = True
            self.exchange.close_ts[m.ticker] = m.close_ts
            if hasattr(self.exchange, "open_ts"):
                self.exchange.open_ts[m.ticker] = m.open_ts
            self.strategy.on_market(ctx, m)
        if m.result is not None:
            info = ctx.markets[m.ticker]
            info.result, info.settle_value = m.result, m.settle_value
            self.exchange.on_close(m.ticker)
            pnl = self.portfolio.settle(m.ticker, m.result)
            self.settlements.append((m.ts, m.ticker, pnl))
            self.strategy.on_settle(ctx, info, pnl)
            ctx.books.pop(m.ticker, None)
            self._tops.pop(m.ticker, None)
            ctx.recorded.pop(m.ticker, None)

    def _maybe_on_book(self, ticker: str, book: Book):
        bb, ba = book.best_bid, book.best_ask
        top = (bb, ba, book.bid_qty(bb) if bb else 0, book.ask_qty(ba) if ba else 0)
        if self._tops.get(ticker) != top:
            self._tops[ticker] = top
            self.strategy.on_book(self.ctx, ticker, book)

    def _synth_book(self, tr: Trade):
        """Trades-only data: the last taker-buy price is the ask, the last taker-sell price is the bid."""
        book = self.ctx.books.get(tr.ticker)
        if book is None:
            return
        if tr.taker == Side.BUY:
            book.no_bids = {1000 - tr.price: tr.qty}
            if book.best_bid is not None and book.best_bid >= tr.price:
                book.yes_bids = {}
        else:
            book.yes_bids = {tr.price: tr.qty}
            if book.best_ask is not None and book.best_ask <= tr.price:
                book.no_bids = {}
        book.valid = True
        self.exchange.on_snapshot(tr.ticker)
        self._maybe_on_book(tr.ticker, book)


class _Idle(Strategy):
    """Stand-in during warm-up."""
