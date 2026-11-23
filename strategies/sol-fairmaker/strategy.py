"""SOL fair-value protected maker: generalises sol-zfav-maker from "|z| >= 1.5 favourites" to every z.

Fair value p = Phi(D / (rv15 * sqrt(tau_eff))), D = spot + basis - strike (basis = strike - our 60 s average before open),
tau_eff = max(tau - 40, 10) because the 60 s settlement average has already locked in part of its variance by the close.
We rest a post-only bid for YES at min(best_bid + 1 tick, floor(p - margin)) and a post-only offer (= bid for NO) at
max(best_ask - 1 tick, ceil(p + margin)), so a fill is always at least `margin` mills better than the model. The margin is
the protection against adverse selection (a trade-through after spot moved): quotes are re-priced every `ttl` seconds off
the latest spot. One entry per market, held to settlement.
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


def _phi(x):
    return 0.5 * (1.0 + math.erf(x / math.sqrt(2.0)))


class FairMaker(Strategy):
    params = {"margin": 20, "start_tau": 600, "stop_tau": 120, "ttl": 15, "rv_scale": 1.0, "pmin": 100, "pmax": 900}

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
        z = (s + self.basis[t] - m.strike) / (rv * math.sqrt(max(tau - 40, 10)))
        p = 1000 * _phi(z)
        if not (self.p.pmin <= p <= self.p.pmax):
            return
        bid, ask = book.best_bid, book.best_ask
        buy_px = min(ask - TICK, bid + TICK, int((p - self.p.margin) // TICK) * TICK)
        sell_px = max(bid + TICK, ask - TICK, -int(-(p + self.p.margin) // TICK) * TICK)
        eb = p - buy_px if buy_px >= TICK else -1
        es = sell_px - p if sell_px <= 1000 - TICK else -1
        if buy_px >= TICK and eb >= self.p.margin and eb >= es:
            qty = ctx.size(t, Side.BUY, buy_px, tif=TIF.POST)
            if qty >= 1 and ctx.buy(t, buy_px, qty, tif=TIF.POST, tag="fm-yes") is not None:
                self.placed[t] = now_s
        elif es >= self.p.margin:
            qty = ctx.size(t, Side.SELL, sell_px, tif=TIF.POST)
            if qty >= 1 and ctx.sell(t, sell_px, qty, tif=TIF.POST, tag="fm-no") is not None:
                self.placed[t] = now_s

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.placed.pop(m.ticker, None)
