"""Simulated Kalshi matching against recorded (or trade-implied) books.

Fill model
----------
* Latency: orders and cancels reach the exchange `latency_ms` after submission, and match
  against the book *at arrival*, not the book the strategy saw.
* Taking: an order crossing the book walks the displayed asks/bids level by level. Liquidity we
  take is remembered per level (the recording doesn't know we took it) until the level is gone.
* Resting: a resting order joins the queue at its price behind `queue_frac` of the size already
  there (1.0 = back of the queue, the conservative default; 0.5 = halfway). It fills only
  when trades print: a trade *through* our price fills us (up to the trade's size); a trade *at*
  our price first eats the queue ahead of us. Cancels ahead of us are ignored, so maker fill
  rates are a lower bound.
* Orders arriving before the market opens or after it closes are rejected; resting orders are
  cancelled at close.
"""

from collections import defaultdict

from ..core.book import Book
from ..core.fees import Fees
from ..core.types import TIF, BookDelta, Fill, Order, Side, Trade

NS_PER_MS = 1_000_000


class SimExchange:
    def __init__(self, latency_ms: float = 150, fees: Fees | None = None, queue_frac: float = 1.0):
        self.latency_ns = int(latency_ms * NS_PER_MS)
        self.queue_frac = queue_frac
        self.fees = fees or Fees()
        self.pending: list[tuple[int, str, Order]] = []  # (arrival_ts, 'new'|'cancel', order)
        self.resting: dict[str, list[Order]] = defaultdict(list)
        self.consumed: dict[tuple[str, str, int], float] = {}  # (ticker, ladder, price) -> qty we took
        self.close_ts: dict[str, int] = {}
        self.open_ts: dict[str, int] = {}

    # --- strategy-facing (via Context) ---------------------------------
    def submit(self, o: Order, now: int):
        self.pending.append((now + self.latency_ns, "new", o))

    def cancel(self, o: Order, now: int):
        self.pending.append((now + self.latency_ns, "cancel", o))

    # --- engine-facing ---------------------------------------------------
    def process_until(self, t: int, books: dict[str, Book]) -> list[Fill]:
        if not self.pending or self.pending[0][0] > t:
            return []
        fills = []
        due = [p for p in self.pending if p[0] <= t]
        self.pending = [p for p in self.pending if p[0] > t]
        for ts, kind, o in due:
            if kind == "cancel":
                if o.is_live:
                    o.status = "cancelled"
                    if o in self.resting[o.ticker]:
                        self.resting[o.ticker].remove(o)
                continue
            if o.status != "pending":
                continue  # cancelled before it arrived
            book = books.get(o.ticker)
            if (book is None or not book.valid or ts >= self.close_ts.get(o.ticker, 1 << 62)
                    or ts < self.open_ts.get(o.ticker, 0)):
                o.status = "rejected"
                continue
            if o.tif == TIF.POST and self._crosses(o, book):
                o.status = "rejected"
                continue
            if o.tif != TIF.POST:
                fills += self._take(o, book, ts)
            if o.remaining > 1e-9 and o.tif in (TIF.GTC, TIF.POST):
                o.status = "open"
                level = book.bid_qty(o.price) if o.side == Side.BUY else book.ask_qty(o.price)
                o.queue_ahead = level * self.queue_frac
                self.resting[o.ticker].append(o)
            elif o.remaining > 1e-9:
                o.status = "cancelled"
        return fills

    def _crosses(self, o: Order, book: Book) -> bool:
        if o.side == Side.BUY:
            return any(px <= o.price and q - self.consumed.get((o.ticker, "no", 1000 - px), 0.0) > 1e-9
                       for px, q in book.asks())
        return any(px >= o.price and q - self.consumed.get((o.ticker, "yes", px), 0.0) > 1e-9
                   for px, q in book.bids())

    def _take(self, o: Order, book: Book, ts: int) -> list[Fill]:
        fills = []
        if o.side == Side.BUY:
            levels, ladder = book.asks(), "no"
            crosses = lambda px: px <= o.price
            key_px = lambda px: 1000 - px
        else:
            levels, ladder = book.bids(), "yes"
            crosses = lambda px: px >= o.price
            key_px = lambda px: px
        for px, qty in levels:
            if o.remaining <= 1e-9 or not crosses(px):
                break
            key = (o.ticker, ladder, key_px(px))
            avail = qty - self.consumed.get(key, 0.0)
            if avail <= 1e-9:
                continue
            q = min(avail, o.remaining)
            self.consumed[key] = self.consumed.get(key, 0.0) + q
            fills.append(self._fill(o, px, q, ts, maker=False))
        return fills

    def _fill(self, o: Order, px: int, q: float, ts: int, maker: bool) -> Fill:
        o.filled += q
        if o.remaining <= 1e-9:
            o.status = "filled"
        return Fill(ts, o.id, o.ticker, o.side, px, q, self.fees(px, q, maker), maker, o.tag)

    def on_delta(self, d: BookDelta, book: Book):
        key = (d.ticker, d.side, d.price)
        if key in self.consumed:
            ladder = book.yes_bids if d.side == "yes" else book.no_bids
            if d.price not in ladder:
                del self.consumed[key]

    def on_snapshot(self, ticker: str):
        for k in [k for k in self.consumed if k[0] == ticker]:
            del self.consumed[k]

    def on_trade(self, tr: Trade) -> list[Fill]:
        fills = []
        for o in list(self.resting.get(tr.ticker, ())):
            if o.side == Side.BUY and tr.taker == Side.SELL and tr.price <= o.price:
                through = tr.price < o.price
            elif o.side == Side.SELL and tr.taker == Side.BUY and tr.price >= o.price:
                through = tr.price > o.price
            else:
                continue
            if through:
                q = min(o.remaining, tr.qty)
            else:
                q = max(0.0, tr.qty - o.queue_ahead)
                o.queue_ahead = max(0.0, o.queue_ahead - tr.qty)
                q = min(q, o.remaining)
            if q > 1e-9:
                fills.append(self._fill(o, o.price, q, tr.ts, maker=True))
                if o.status == "filled":
                    self.resting[tr.ticker].remove(o)
        return fills

    def on_close(self, ticker: str):
        for o in self.resting.pop(ticker, []):
            o.status = "cancelled"
        for _, _, o in self.pending:
            if o.ticker == ticker and o.status == "pending":
                o.status = "rejected"
        self.on_snapshot(ticker)
