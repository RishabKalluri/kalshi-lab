"""SOL zfav maker with gap-proportional sizing: sol-zfav-early's post-only favourite bid (540..300 s to close), but the entry
and the size come from the gap between the spot-implied probability Phi(z) and the price we would pay.

Why: across the zfav maker family the per-contract edge is large where the quote is far below what spot confirmation implies
(favourite <=90c: +5..8c) and ~0.6-1.5c near 95-97c, where the fee-free spread is already competed. A flat z cut and flat
sizing put as much money on the 97c fills as on the 85c ones. Here we estimate the win probability as
prob = px + k*(Phi(z) - px) (k = shrink, fixed a priori at 0.5), skip when Phi(z) - px < gmin, and let kelly sizing
(sizing "kelly:F") turn prob into contracts, so size grows with the gap.

z = D / (rv15 * sqrt(tau)), D = spot + basis - strike, as in sol-zfav-early.
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
TICK = 10  # mills (1 cent)


class ZFavKelly(Strategy):
    params = {"zmin": 1.0, "gmin": 0.03, "k": 0.5, "max_px": 970, "start_tau": 540, "stop_tau": 300, "ttl": 30, "rv_scale": 1.0}

    def on_start(self, ctx):
        self.hist, self.basis, self.done, self.placed = {}, {}, set(), {}
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
        if t in self.done or t not in self.basis:
            return
        if ctx.position(t) != 0:
            self.done.add(t)
            ctx.cancel_all(t)
            return
        if tau < self.p.stop_tau:
            ctx.cancel_all(t)
            return
        if tau > self.p.start_tau:
            return
        h = self.hist.get(m.series)
        n = min(900, len(h.cum) - 1) if h else 0
        book = ctx.book(t)
        if n < 450 or book is None or book.best_bid is None or book.best_ask is None:
            return
        live = ctx.open_orders(t)
        if live and now_s - self.placed.get(t, 0) < self.p.ttl:
            return
        ctx.cancel_all(t)
        rv = math.sqrt((h.cum[-1] - h.cum[-1 - n]) / n) * self.p.rv_scale
        s = ctx.spot(series=m.series)
        if rv <= 0 or s is None:
            return
        z = (s + self.basis[t] - m.strike) / (rv * math.sqrt(tau))
        bid, ask = book.best_bid, book.best_ask
        phi = 0.5 * (1 + math.erf(abs(z) / math.sqrt(2)))  # P(favourite wins) under the driftless normal model
        if z >= self.p.zmin:
            px = min(ask - TICK, bid + TICK)
            gap = phi - px / 1000
            if px <= self.p.max_px and px >= TICK and gap >= self.p.gmin:
                prob = px / 1000 + self.p.k * gap
                qty = ctx.size(t, Side.BUY, px, prob=prob, tif=TIF.POST)
                if qty >= 1 and ctx.buy(t, px, qty, tif=TIF.POST, tag="zm-yes") is not None:
                    self.placed[t] = now_s
        elif z <= -self.p.zmin:
            px = max(bid + TICK, ask - TICK)
            gap = phi - (1000 - px) / 1000
            if 1000 - px <= self.p.max_px and px <= 1000 - TICK and gap >= self.p.gmin:
                prob = 1 - ((1000 - px) / 1000 + self.p.k * gap)  # P(YES) when we sell YES
                qty = ctx.size(t, Side.SELL, px, prob=prob, tif=TIF.POST)
                if qty >= 1 and ctx.sell(t, px, qty, tif=TIF.POST, tag="zm-no") is not None:
                    self.placed[t] = now_s

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.placed.pop(m.ticker, None)
