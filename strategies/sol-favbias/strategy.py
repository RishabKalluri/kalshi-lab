"""Favourite-bias taker: buy the 90-95c favourite (YES or NO) once per market, 5-12 minutes before close.

Across all five coins' 15-minute markets the 90-95c favourite wins about 0.7 points more often than its price
(plus fee) implies in research; underdog buyers overpay for tails, so the favourite is slightly cheap. Hold to
settlement. Prices are YES mills (0..1000); ctx.buy = buy YES, ctx.sell = sell YES (= buy NO).
"""

from kalshi_lab.core.types import TIF, Side
from kalshi_lab.strategy import Strategy


class FavBias(Strategy):
    params = {"lo": 900, "hi": 950, "h_min": 300, "h_max": 720}

    def on_start(self, ctx):
        self.done = set()

    def on_timer(self, ctx):
        p = self.p
        for m in ctx.active_markets():
            t = m.ticker
            if t in self.done:
                continue
            left = ctx.seconds_left(t)
            if left is None or left > p.h_max or left < p.h_min:
                continue
            book = ctx.book(t)
            if book is None:
                continue
            ask, bid = book.best_ask, book.best_bid
            if ask is not None and p.lo < ask <= p.hi:
                qty = ctx.size(t, Side.BUY, ask, tif=TIF.IOC)
                if qty >= 1:
                    ctx.buy(t, ask, qty, tif=TIF.IOC, tag="fav-yes")
                    self.done.add(t)
            elif bid is not None and p.lo < 1000 - bid <= p.hi:
                qty = ctx.size(t, Side.SELL, bid, tif=TIF.IOC)
                if qty >= 1:
                    ctx.sell(t, bid, qty, tif=TIF.IOC, tag="fav-no")
                    self.done.add(t)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
