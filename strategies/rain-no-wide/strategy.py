"""Rain NO: buy NO on "Will it rain in <city> on <date>?" markets in the last hours of the local day when retail still holds YES.

The rule is "total precipitation at the NWS station strictly greater than 0 inches": trace amounts and rain that
misses the airport gauge resolve NO, while retail prices the forecast chance of rain and keeps paying for the lottery
ticket through the evening. Development takers (Jul 16 - Aug 31, 42 days, ~830 city-days) lost 10-18c per contract buying YES
at 10-90c within 12 h of the close and NO takers earned +10..+15c; a fixed-rule engine run (below) confirmed it.
v2 (this file's defaults): in the last `max_ttc_h` hours before the close (markets close at local midnight), the first time
a taker hits the YES bid while it is in [lo, hi], buy NO at that bid (IOC), one entry per city-day, held to settlement.
v1 (min_ttc_h 2.5, max_ttc_h 24, lo 50, hi 600, any trade) is kept in NOTES.md (full: +3.4c, CI -0.9..+7.6).

Prices are YES mills. ctx.sell(YES) = buy NO.
"""

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402


class RainNoWide(Strategy):
    params = {
        "lo": 100,          # trade when the YES bid is in [lo, hi] mills (NO costs 1000 - bid)
        "hi": 750,
        "min_ttc_h": 6.0,   # complement of rain-no: only the earlier hours (rain-no trades the last 6 h)
        "max_ttc_h": 30.0,  # markets list ~36 h before the close
        "max_spread": 300,  # ask - bid, mills: skip stale/one-sided synthetic books
    }

    def on_start(self, ctx):
        self.done = set()

    def on_trade(self, ctx, tr):
        # history has trades but no books: the engine synthesizes the top of book from each trade, so evaluate there
        m = ctx.markets.get(tr.ticker)
        if m is None or m.result is not None or tr.taker != Side.SELL:
            return  # only a taker hitting the bid proves where the bid is now (the synthetic bid is otherwise stale)
        for m in (m,):
            t = m.ticker
            if t in self.done:
                continue
            h = ctx.seconds_left(t) / 3600
            if h > self.p.max_ttc_h or h < self.p.min_ttc_h:
                continue
            book = ctx.book(t)
            if book is None or book.best_bid is None or book.best_ask is None:
                continue
            bid, ask = book.best_bid, book.best_ask
            if not (self.p.lo <= bid <= self.p.hi) or ask - bid > self.p.max_spread:
                continue
            qty = ctx.size(t, Side.SELL, bid, tif=TIF.IOC)
            if qty < 1:
                continue
            o = ctx.sell(t, bid, qty, tif=TIF.IOC, tag="no")
            if o is not None:
                self.done.add(t)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
