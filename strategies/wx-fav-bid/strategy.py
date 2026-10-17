"""Weather favourite bid: rest post-only quotes on the shape of each KXHIGH city-day ladder, early in the market's life.

Reading prices of the ten KXHIGH series at fixed hours before the close (335 days, trades): the ladder is too wide. The
favourite bracket's outcome rate beats its mid by ~3.5c at 24 h and the neighbours (rank 2-6) are 1.4-2.5c overpriced;
implied variance is ~1.4x the realized squared error. Takers can't harvest it (spread + fee ~ the edge), a maker with no
fee can: bid on the favourite at the touch, offer the ranks 2-3 (sides=both), hold to settlement. wx-maker only quoted
mid 5-50c, so it never bid the favourite. v1 quoted 12-34 h before the close; its fills lost 5c/ct at 12-16 h and made
+2c/ct at 28-40 h (ad hoc, 10 cities Jan-Aug), as the fixed-time screen predicted (edge fades as the day approaches):
v2 quotes 26-40 h before the close.

Prices are YES mills. ctx.buy = bid for YES, ctx.sell = offer of YES.
"""

from kalshi_lab.core.types import TIF  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class WxFavBid(Strategy):
    params = {
        "max_h": 40.0,     # quote from this many hours before the close...
        "min_h": 26.0,     # ...until this many (the ladder is sharp later)
        "min_mid": 300,    # favourite's mid must be at least this (mills)
        "sides": "bid",    # bid = favourite only; both = also offer ranks 2..ask_rank
        "ask_rank": 3,
        "min_ask_mid": 100,
        "back": 0,         # ticks (cents) behind the touch
        "max_pos": 30,     # max contracts per bracket
        "qty": 10,
        "every_s": 10,
    }

    def on_start(self, ctx):
        self.q = {}        # (ticker, side) -> live order

    @staticmethod
    def _event(ticker):
        return ticker.rsplit("-", 1)[0]

    def on_timer(self, ctx):
        if (ctx.now // NS) % self.p.every_s:
            return
        groups = {}
        for m in ctx.active_markets():
            h = ctx.seconds_left(m.ticker) / 3600
            if self.p.min_h <= h <= self.p.max_h:
                groups.setdefault(self._event(m.ticker), []).append(m)
        want = {}   # (ticker, side) -> price
        for ev, ms in groups.items():
            if len(ms) < 4:
                continue
            rows = []
            for m in ms:
                b = ctx.book(m.ticker)
                if b is None or b.best_bid is None or b.best_ask is None:
                    continue
                rows.append(((b.best_bid + b.best_ask) / 2, m.ticker, b))
            rows.sort(reverse=True)
            if not rows or rows[0][0] < self.p.min_mid:
                continue
            mid, t, b = rows[0]
            px = b.best_bid - 10 * self.p.back
            if px >= 10:
                want[(t, "bid")] = px
            if self.p.sides == "both":
                for mid, t, b in rows[1:self.p.ask_rank]:
                    if mid >= self.p.min_ask_mid:
                        want[(t, "ask")] = b.best_ask + 10 * self.p.back
        for k, o in list(self.q.items()):
            if not o.is_live:
                self.q.pop(k)
            elif want.get(k) != o.price:
                ctx.cancel(o)
                self.q.pop(k)
        for (t, side), px in want.items():
            if (t, side) in self.q:
                continue
            pos = ctx.position(t)
            if side == "bid" and pos < self.p.max_pos:
                o = ctx.buy(t, px, self.p.qty, tif=TIF.POST, tag="fav")
            elif side == "ask" and pos > -self.p.max_pos:
                o = ctx.sell(t, px, self.p.qty, tif=TIF.POST, tag="nbr")
            else:
                continue
            if o is not None:
                self.q[(t, side)] = o

    def on_settle(self, ctx, m, pnl):
        self.q.pop((m.ticker, "bid"), None)
        self.q.pop((m.ticker, "ask"), None)
