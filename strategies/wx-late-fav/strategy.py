"""KXHIGH late-afternoon favourite carry: buy the bracket priced 85-97c 6-10 h before the close, hold to settlement.

Development trades (10 cities, Oct 2025 - Aug 2026) showed favourites bought 6-10 h before the local-midnight close
at 85-98c winning more often than priced (+1..+3c after fees at trade prices), while the 4-6 h bucket was negative.
Entry: the first taker BUY (which proves the ask) in the window with price in [lo, hi]; IOC at the ask; one entry per
bracket. Prices are YES mills.
"""

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402


class WxLateFav(Strategy):
    params = {"lo": 850, "hi": 970, "min_ttc_h": 6.0, "max_ttc_h": 10.0, "max_spread": 30}

    def on_start(self, ctx):
        self.done = set()

    def on_trade(self, ctx, tr):
        m = ctx.markets.get(tr.ticker)
        if m is None or m.result is not None or tr.taker != Side.BUY or tr.ticker in self.done:
            return
        h = ctx.seconds_left(tr.ticker) / 3600
        if not (self.p.min_ttc_h <= h <= self.p.max_ttc_h):
            return
        book = ctx.book(tr.ticker)
        if book is None or book.best_ask is None or book.best_bid is None:
            return
        ask = book.best_ask
        if not (self.p.lo <= ask <= self.p.hi) or ask - book.best_bid > self.p.max_spread:
            return
        qty = ctx.size(tr.ticker, Side.BUY, ask, tif=TIF.IOC)
        if qty < 1:
            return
        if ctx.buy(tr.ticker, ask, qty, tif=TIF.IOC, tag="fav") is not None:
            self.done.add(tr.ticker)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
