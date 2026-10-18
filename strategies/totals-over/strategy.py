"""Totals over: buy YES on NBA/MLB total-points/runs "over X" markets at the ask shortly after the market starts trading.

Fixed-time screen on the 150-market samples (pre-game, 20-80c): NBA +7.5c, MLB +6.5c (se ~4c, both halves positive) gross of fee: YES (over) is
underpriced. A taker BUY trade proves the ask. Age is measured from the market's first trade (close_ts is outcome-dependent on early-close markets: no lookahead).
Prices are YES mills.
"""

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class TotalsOver(Strategy):
    params = {
        "lo": 200,
        "hi": 800,
        "max_age_h": 6.0,    # hours since the market's first trade
        "max_spread": 300,
    }

    def on_start(self, ctx):
        self.first = {}
        self.done = set()

    def on_trade(self, ctx, tr):
        t = tr.ticker
        self.first.setdefault(t, ctx.now)
        if t in self.done or tr.taker != Side.BUY:
            return
        m = ctx.markets.get(t)
        if m is None or m.result is not None:
            return
        if (ctx.now - self.first[t]) / NS / 3600 > self.p.max_age_h:
            return
        book = ctx.book(t)
        if book is None or book.best_bid is None or book.best_ask is None:
            return
        bid, ask = book.best_bid, book.best_ask
        if not (self.p.lo <= ask <= self.p.hi) or ask - bid > self.p.max_spread:
            return
        qty = ctx.size(t, Side.BUY, ask, tif=TIF.IOC)
        if qty < 1:
            return
        if ctx.buy(t, ask, qty, tif=TIF.IOC, tag="over") is not None:
            self.done.add(t)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.first.pop(m.ticker, None)
