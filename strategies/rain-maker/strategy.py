"""Rain maker / real-book check of rain-no: sell YES (= buy NO) on KXRAIN city-days when the YES bid is mid-range.

rain-no (taker, trade-synthesized book) found retail overpays YES on "will it rain" (strict >0.00 in at the station).
Recorded-style order books exist for KXRAIN since Jul 16 (backfill/books), so this runs on real quotes (config "source": "books").
mode=taker : once per market, in the last [min_h, max_h] hours, hit the YES bid (IOC) if it is in [lo, hi] and the spread <= max_spread.
mode=maker : in the same window, rest a post-only offer of YES at the best ask (+back cents) when the bid is in [lo, hi]; keep it until the
             window ends; a fill is a retail YES buyer paying the ask. No fee for makers on weather.

Prices are YES mills. ctx.sell = offer YES (= buy NO).
"""

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class RainMaker(Strategy):
    params = {
        "mode": "maker",    # maker | taker
        "lo": 100,          # trade when the YES bid is in [lo, hi] mills
        "hi": 900,
        "min_h": 0.5,
        "max_h": 6.0,
        "max_spread": 300,  # taker only
        "back": 0,          # maker: cents behind the touch
        "max_pos": 40,      # maker: max contracts short per market
        "every_s": 5,
    }

    def on_start(self, ctx):
        self.q = {}
        self.done = set()

    def on_timer(self, ctx):
        if (ctx.now // NS) % self.p.every_s:
            return
        for m in ctx.active_markets():
            t = m.ticker
            h = ctx.seconds_left(t) / 3600
            o = self.q.get(t)
            b = ctx.book(t)
            ok = (b is not None and b.best_bid is not None and b.best_ask is not None
                  and self.p.min_h <= h <= self.p.max_h and self.p.lo <= b.best_bid <= self.p.hi)
            if self.p.mode == "taker":
                if ok and t not in self.done and b.best_ask - b.best_bid <= self.p.max_spread:
                    qty = ctx.size(t, Side.SELL, b.best_bid, tif=TIF.IOC)
                    if qty >= 1 and ctx.sell(t, b.best_bid, qty, tif=TIF.IOC, tag="no") is not None:
                        self.done.add(t)
                continue
            if o is not None and not o.is_live:
                self.q.pop(t); o = None
            px = b.best_ask + 10 * self.p.back if ok else None
            if o is not None and (px is None or o.price != px):
                ctx.cancel(o); self.q.pop(t); o = None
            if px is not None and o is None and ctx.position(t) > -self.p.max_pos:
                qty = ctx.size(t, Side.SELL, px, tif=TIF.POST)
                n = ctx.sell(t, px, qty, tif=TIF.POST, tag="ask") if qty >= 1 else None
                if n is not None:
                    self.q[t] = n

    def on_settle(self, ctx, m, pnl):
        self.q.pop(m.ticker, None)
