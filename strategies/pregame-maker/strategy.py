"""Pregame maker: post-only quotes on sports game-winner markets before the game starts, pulled before tip-off.

Takers pay the spread (and the sport's taker fee) before the game and prices are calibrated (longshot-fade), so the
money, if any, is the touch spread minus the maker fee (0.0175*p*(1-p), rounded up) minus adverse selection from news
(injuries, lineups). v1: join the best bid and best ask while the price is inside a band, from `quote_h` hours before
the estimated start until `pull_min` minutes before it, pull a side after a fast mid move, and cap the net exposure of
each game (the two teams' markets are one outcome).

Game start is estimated from the market's expected_expiration_time minus `exp_lead_min` (NBA/NHL: median 168 min, 90%
within 162-172), so the same rule runs in backtests, paper and live without a schedule feed.

Prices are YES mills. ctx.buy = bid for YES, ctx.sell = offer of YES (= buy NO).
"""

from collections import deque
from datetime import datetime

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


def _ts(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()) * NS


class PregameMaker(Strategy):
    params = {
        "exp_lead_min": 171,   # est. start = expected_expiration - this (conservative: early)
        "quote_h": 6.0,        # start quoting this many hours before the estimated start
        "pull_min": 8.0,       # cancel everything this many minutes before the estimated start
        "min_px": 100,         # quote a side only if its price (bid, or ask for the offer) is in [min_px, max_px]
        "max_px": 900,
        "min_spread": 0,       # quote only when the touch spread (mills) is at least this wide
        "improve": 0,          # ticks to improve on the touch when spread >= 30 (0 = join the touch)
        "flow_w": 0,           # s of taker flow to look back (0 = off): don't quote the side the recent flow hits
        "flow_thr": 0.6,       # |signed share of taker volume| above which the hit side is pulled
        "flow_min": 500,       # ...if at least this many contracts traded in the window
        "tails": 0,            # 1 = quote only the extremes: bid a favourite (bid >= 1000-tail_px), offer a longshot
        "tail_px": 100,
        "sides": "both",       # both | bid | ask
        "pull_move": 20,       # pull a side when the mid moved this many mills within move_s
        "move_s": 300,
        "cooldown_s": 600,
        "ev_cap": 200,         # max |net exposure| (contracts) per game
        "max_pos": 100,        # max |position| per market
        "qty": 20,             # contracts per quote (ctx.size is used if qty == 0)
    }

    def on_start(self, ctx):
        self.quotes = {}      # ticker -> {"bid": Order, "ask": Order}
        self.mids = {}        # ticker -> deque[(t, mid)]
        self.pulled = {}      # (ticker, side) -> until
        self.start = {}       # ticker -> estimated start ns (None = unknown)
        self.flow = {}        # ticker -> deque[(t, signed qty)] of recent taker trades
        self.event = {}       # ticker -> event ticker
        self.sibs = {}        # event ticker -> [tickers]

    def _info(self, m):
        if m.ticker in self.start:
            return self.start[m.ticker]
        exp = (m.raw or {}).get("expected_expiration_time")
        s = _ts(exp) - int(self.p.exp_lead_min * 60 * NS) if exp else None
        self.start[m.ticker] = s
        ev = m.ticker.rsplit("-", 1)[0]
        self.event[m.ticker] = ev
        self.sibs.setdefault(ev, []).append(m.ticker)
        return s

    def on_trade(self, ctx, t):
        if not self.p.flow_w:
            return
        d = self.flow.setdefault(t.ticker, deque())
        d.append((t.ts, t.qty if t.taker == Side.BUY else -t.qty))
        while d and d[0][0] < t.ts - int(self.p.flow_w * NS):
            d.popleft()

    def _flow(self, ctx, ticker):
        """(signed share of taker volume, contracts) over the last flow_w seconds."""
        d = self.flow.get(ticker)
        if not d:
            return 0.0, 0.0
        cut = ctx.now - int(self.p.flow_w * NS)
        while d and d[0][0] < cut:
            d.popleft()
        tot = sum(abs(q) for _, q in d)
        return (sum(q for _, q in d) / tot if tot else 0.0), tot

    def _cancel(self, ctx, ticker, side):
        o = self.quotes.get(ticker, {}).pop(side, None)
        if o is not None and o.is_live:
            ctx.cancel(o)

    def _net(self, ctx, ev, ticker):
        """Net exposure of the game in 'first market's YES' units (YES in A == NO in B)."""
        tk = self.sibs[ev]
        return sum(ctx.position(t) * (1 if t == tk[0] else -1) for t in tk), (1 if ticker == tk[0] else -1)

    def on_timer(self, ctx):
        now = ctx.now
        for m in ctx.active_markets():
            s = self._info(m)
            if s is None:
                continue
            q = self.quotes.get(m.ticker)
            if now < s - int(self.p.quote_h * 3600 * NS):
                continue
            if now >= s - int(self.p.pull_min * 60 * NS):
                if q:
                    for side in list(q):
                        self._cancel(ctx, m.ticker, side)
                continue
            book = ctx.book(m.ticker)
            if book is None or book.best_bid is None or book.best_ask is None:
                continue
            bid, ask = book.best_bid, book.best_ask
            mid = (bid + ask) / 2
            spread = ask - bid
            h = self.mids.setdefault(m.ticker, deque())
            h.append((now, mid))
            while len(h) > 1 and h[1][0] <= now - int(self.p.move_s * NS):
                h.popleft()
            move = mid - h[0][1]
            if move >= self.p.pull_move:       # YES jumped up: our offer is stale
                self.pulled[(m.ticker, "ask")] = now + int(self.p.cooldown_s * NS)
            elif move <= -self.p.pull_move:
                self.pulled[(m.ticker, "bid")] = now + int(self.p.cooldown_s * NS)
            pos = ctx.position(m.ticker)
            ev = self.event[m.ticker]
            net, sgn = self._net(ctx, ev, m.ticker)
            if self.p.improve and spread >= 30:
                bid, ask = bid + 10 * self.p.improve, ask - 10 * self.p.improve
            wide = spread >= self.p.min_spread
            if self.p.tails:  # only the cheap-fee extremes: bid a favourite, offer a longshot
                lo_ok, hi_ok = ask <= self.p.tail_px, bid >= 1000 - self.p.tail_px
            else:
                lo_ok = hi_ok = True
            if self.p.flow_w:
                fl, tot = self._flow(ctx, m.ticker)
                if tot >= self.p.flow_min:
                    if fl >= self.p.flow_thr:        # buyers lifting offers: our offer is the one being picked off
                        self.pulled[(m.ticker, "ask")] = max(self.pulled.get((m.ticker, "ask"), 0), now + NS)
                    elif fl <= -self.p.flow_thr:
                        self.pulled[(m.ticker, "bid")] = max(self.pulled.get((m.ticker, "bid"), 0), now + NS)
            want = {"bid": bid if wide and hi_ok and self.p.min_px <= bid <= self.p.max_px
                    and self.p.sides in ("both", "bid")
                    and pos < self.p.max_pos and net * sgn < self.p.ev_cap else None,
                    "ask": ask if wide and lo_ok and self.p.min_px <= ask <= self.p.max_px
                    and self.p.sides in ("both", "ask")
                    and pos > -self.p.max_pos and -net * sgn < self.p.ev_cap else None}
            q = self.quotes.setdefault(m.ticker, {})
            for side, px in want.items():
                if self.pulled.get((m.ticker, side), 0) > now:
                    px = None
                cur = q.get(side)
                if cur is not None and not cur.is_live:
                    q.pop(side)
                    cur = None
                if px is None:
                    if cur is not None:
                        self._cancel(ctx, m.ticker, side)
                    continue
                if cur is not None and cur.price == px:
                    continue  # keep queue position
                if cur is not None:
                    self._cancel(ctx, m.ticker, side)
                s_ = Side.BUY if side == "bid" else Side.SELL
                qty = self.p.qty or ctx.size(m.ticker, s_, px, tif=TIF.POST)
                if qty < 1:
                    continue
                o = (ctx.buy if side == "bid" else ctx.sell)(m.ticker, px, qty, tif=TIF.POST, tag=side)
                if o is not None:
                    q[side] = o

    def on_settle(self, ctx, m, pnl):
        self.quotes.pop(m.ticker, None)
        self.mids.pop(m.ticker, None)
        for side in ("bid", "ask"):
            self.pulled.pop((m.ticker, side), None)
