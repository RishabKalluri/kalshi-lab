"""Minimal market maker: rest a bid and an ask `half_spread` around model fair value, skewed
against inventory. Shows the maker side of the API (GTC orders, cancel/replace, on_fill).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fair_value import FairValue  # noqa: E402

from kalshi_lab.core.types import TIF, Side  # noqa: E402

NS = 1_000_000_000


class Quoter(FairValue):
    params = {
        **FairValue.params,
        "half_spread": 30,   # mills each side of fair
        "skew": 2,           # mills of price shift per contract of inventory
        "requote": 15,       # replace a quote once fair moves this many mills
        "min_tau": 60,
    }

    def on_start(self, ctx):
        super().on_start(ctx)
        self.quotes: dict[str, dict] = {}  # ticker -> {'bid': Order, 'ask': Order}

    def on_timer(self, ctx):
        # Reuse FairValue's bookkeeping to compute self.fair, but never let it take.
        edge, self.p.edge = self.p.edge, 10**9
        super().on_timer(ctx)
        self.p.edge = edge
        for m in ctx.active_markets():
            fair = self.fair.get(m.ticker)
            tau = (m.close_ts - ctx.now) / NS
            q = self.quotes.setdefault(m.ticker, {})
            if fair is None or not (self.p.min_tau <= tau <= self.p.max_tau):
                for o in q.values():
                    ctx.cancel(o)
                q.clear()
                continue
            pos = ctx.position(m.ticker)
            center = fair - self.p.skew * pos
            want = {"bid": int(center - self.p.half_spread), "ask": int(center + self.p.half_spread) + 1}
            for side, px in want.items():
                px = max(10, min(990, px))
                o = q.get(side)
                if o is not None and o.is_live and abs(o.price - px) < self.p.requote:
                    continue
                if o is not None and o.is_live:
                    ctx.cancel(o)
                room = self.p.max_pos - pos if side == "bid" else self.p.max_pos + pos
                if room < 1:
                    q.pop(side, None)
                    continue
                fn = ctx.buy if side == "bid" else ctx.sell
                qty = min(ctx.size(m.ticker, Side.BUY if side == "bid" else Side.SELL, px, prob=fair / 1000), room)
                if qty < 1:
                    continue
                new = fn(m.ticker, px, qty, tif=TIF.GTC, tag=side)
                if new:
                    q[side] = new

    def on_settle(self, ctx, m, pnl):
        super().on_settle(ctx, m, pnl)
        self.quotes.pop(m.ticker, None)
