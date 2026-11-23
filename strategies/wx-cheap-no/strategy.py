"""KXHIGH cheap-bracket NO: hit the YES bid (buy NO) on 2-12c brackets 18-36 h before the close, hold to settlement.

The 6-bracket ladder is quoted too wide a day ahead (implied variance ~1.4x realized), so far brackets priced 2-12c
resolve YES less often than priced. Development screen (taker-sell prints, 10 cities): NO at the proven bid nets
+0.9c/ct (se 0.35-0.6) for 18-36 h before close, ~0 or negative closer and earlier. One entry per bracket; the trigger is
a taker SELL print (it proves the bid). Prices are YES mills; ctx.sell(YES) = buy NO.
"""

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402


class WxCheapNo(Strategy):
    params = {"lo": 20, "hi": 120, "min_ttc_h": 18.0, "max_ttc_h": 36.0}

    def on_start(self, ctx):
        self.done = set()

    def on_trade(self, ctx, tr):
        m = ctx.markets.get(tr.ticker)
        if m is None or m.result is not None or tr.taker != Side.SELL or tr.ticker in self.done:
            return
        h = ctx.seconds_left(tr.ticker) / 3600
        if not (self.p.min_ttc_h <= h <= self.p.max_ttc_h):
            return
        book = ctx.book(tr.ticker)
        if book is None or book.best_bid is None:
            return
        bid = book.best_bid
        if not (self.p.lo <= bid <= self.p.hi):
            return
        qty = ctx.size(tr.ticker, Side.SELL, bid, tif=TIF.IOC)
        if qty < 1:
            return
        if ctx.sell(tr.ticker, bid, qty, tif=TIF.IOC, tag="no") is not None:
            self.done.add(tr.ticker)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
