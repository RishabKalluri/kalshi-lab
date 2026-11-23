"""sol-zfav-cheap: sol-zfav-early restricted (max_px=900) to favourites costing <= 90c; see NOTES.md.

SOL spot-confirmed favourite with a maker entry: sol-zfav's signal (spot >= zmin sigma past the strike), but instead of
lifting the ask we rest a post-only order one tick inside the spread on the favourite's side, between 420 s and 150 s to close.

Why: sol-zfav's taker rule nets about -0.5c on Jun-Sep development data because the fee (about 0.6c at 90c) and half the spread
eat the +1..3c the confirmed favourite is worth. A maker pays no fee and earns the spread. Adverse selection is the risk: a
resting bid fills when a seller hits it, and on a confirmed favourite that seller is mostly a nervous holder, not informed flow.
One entry per market, held to settlement; unfilled orders are cancelled after `ttl` seconds and re-priced, and all are
cancelled at `stop_tau`.

z = D / (rv15 * sqrt(tau)), D = spot + basis - strike (basis = strike - our 60s average before open), rv15 = trailing
15-minute realized vol of 1s spot (same as sol-zfav).
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


class ZFavEarly(Strategy):
    params = {"zmin": 1.5, "max_px": 970, "start_tau": 540, "stop_tau": 300, "ttl": 30, "rv_scale": 1.0}

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
        if z >= self.p.zmin:
            px = min(ask - TICK, bid + TICK)
            if px <= self.p.max_px and px >= TICK:
                qty = ctx.size(t, Side.BUY, px, tif=TIF.POST)
                if qty >= 1 and ctx.buy(t, px, qty, tif=TIF.POST, tag="zm-yes") is not None:
                    self.placed[t] = now_s
        elif z <= -self.p.zmin:
            px = max(bid + TICK, ask - TICK)
            if 1000 - px <= self.p.max_px and px <= 1000 - TICK:
                qty = ctx.size(t, Side.SELL, px, tif=TIF.POST)
                if qty >= 1 and ctx.sell(t, px, qty, tif=TIF.POST, tag="zm-no") is not None:
                    self.placed[t] = now_s

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.placed.pop(m.ticker, None)
