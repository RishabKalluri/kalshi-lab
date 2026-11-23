"""Spot-confirmed favourite, wide price range: btc-zfav's rule on all five coins, z >= 2.5 at 120-480 s left, ask up to 98.5c.

z = D / (rv15 * sqrt(tau)) as in btc-zfav. Dev screen (research dataset, Dec-Aug, next-fill prices net of fee, earliest
qualifying checkpoint per market): 9,563 entries (35/day), +1.34c (se 0.13), 9/9 months, every coin positive. The earlier
zfav members capped the ask at 97c and traded fewer checkpoints; favourites at 97-98.5c are underpriced too.
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent / "eth-volfav"))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402
from strategy import _Hist  # noqa: E402,F401  (eth-volfav's O(1) realized-vol window)

NS = 1_000_000_000


class ZFavWide(Strategy):
    params = {"zmin": 2.5, "max_px": 985, "checkpoints": [480, 420, 360, 300, 240, 180, 120], "rv_scale": 1.0}

    def on_start(self, ctx):
        self.hist, self.basis, self.done = {}, {}, set()
        if ctx.spot_history:
            for series in ctx.spot_map:
                h = self.hist.setdefault(series, _Hist())
                for sec, px in ctx.spot_history(series, 3600):
                    h.add(sec, px)

    def on_timer(self, ctx):
        now_s = ctx.now // NS
        for series in ctx.spot_map:
            s = ctx.spot(series=series)
            if s is not None:
                self.hist.setdefault(series, _Hist()).add(now_s, s)
        for m in ctx.markets.values():
            if m.ticker in self.basis or m.strike is None or ctx.now < m.open_ts:
                continue
            h = self.hist.get(m.series)
            pre = h.window(m.open_ts // NS - 60, m.open_ts // NS) if h else []
            if len(pre) >= 30:
                self.basis[m.ticker] = m.strike - sum(pre) / len(pre)
        for m in ctx.active_markets():
            self._consider(ctx, m, now_s)

    def _consider(self, ctx, m, now_s):
        t = m.ticker
        tau = (m.close_ts - ctx.now) / NS
        if t in self.done or t not in self.basis or int(round(tau)) not in self.p.checkpoints:
            return
        h = self.hist.get(m.series)
        n = min(900, len(h.cum) - 1) if h else 0
        book = ctx.book(t)
        if n < 450 or book is None or book.best_bid is None or book.best_ask is None:
            return
        rv = math.sqrt((h.cum[-1] - h.cum[-1 - n]) / n) * self.p.rv_scale
        s = ctx.spot(series=m.series)
        if rv <= 0 or s is None:
            return
        z = (s + self.basis[t] - m.strike) / (rv * math.sqrt(tau))
        if z >= self.p.zmin and book.best_ask <= self.p.max_px:
            qty = ctx.size(t, Side.BUY, book.best_ask, tif=TIF.IOC)
            if qty >= 1:
                ctx.buy(t, book.best_ask, qty, tif=TIF.IOC, tag="z-yes")
                self.done.add(t)
        elif z <= -self.p.zmin and 1000 - book.best_bid <= self.p.max_px:
            qty = ctx.size(t, Side.SELL, book.best_bid, tif=TIF.IOC)
            if qty >= 1:
                ctx.sell(t, book.best_bid, qty, tif=TIF.IOC, tag="z-no")
                self.done.add(t)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
