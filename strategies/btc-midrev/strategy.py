"""BTC late-confirmed reversal (btc-midrev): eth-midrev's LateConfirmed rule on KXBTC15M, unchanged, plus an optional
basket filter (H2, default off) that requires BTC, ETH and SOL to have burst into the boundary together.

Original eth-midrev docstring follows.

Late-confirmed reversal: fade the previous window's big move at the open, only when the move ran into the boundary.

15-minute crypto returns reverse in sign after big moves (eth-overreact), and the reversal is U-shaped in the clock:
strongest for moves that end at a 15-minute boundary (research/offset_rev.py). Splitting eth-overreact's trigger
(|z15| > 1.5) by whether the last 5 minutes before the open moved the same way strongly (|z5| > 1.5): the
late-confirmed half made +6.3/+5.1c (Jan-Apr / May-Aug) at next real fills after fee, the rest +2.9/+0.1c; SOL shows
the same split (+7.7/+9.7 vs +8.0/+1.2). So the part of the reversal that survived into May-Aug is the burst into
the boundary (candle-close traders, hedgers of 15-minute binaries rebalancing into expiry, then unwinding).

  z15   = (K_this - K_prev) / (rv_60m * 30)          previous window's move in CF terms (strike to strike)
  z5    = (A(open) - A(open - 300)) / (rv_60m * sqrt(300)),  A = 60 s spot average ending at t (own spot feed)
  entry at fixed checkpoints h = 870/840/810/780 s, once per market: |z15| > z_thr, |z5| > late_thr, same sign,
        mid within [lo, hi] -> buy the reversal side at the touch (IOC, slip_c cents through). Hold to settlement.
"""

import bisect
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class _Hist:
    """1 s spot samples for the last ~1-2 h, running sums of price and squared changes."""
    KEEP = 3600 + 600

    def __init__(self):
        self.secs, self.px, self.cum, self.csum = [], [], [0.0], [0.0]

    def add(self, sec, price):
        if self.secs and sec <= self.secs[-1]:
            return
        if self.px:
            self.cum.append(self.cum[-1] + (price - self.px[-1]) ** 2)
        self.secs.append(sec)
        self.px.append(price)
        self.csum.append(self.csum[-1] + price)
        if len(self.secs) > 2 * self.KEEP:
            k = len(self.secs) - self.KEEP
            self.secs, self.px = self.secs[k:], self.px[k:]
            b1, b2 = self.cum[k], self.csum[k]
            self.cum = [0.0] + [c - b1 for c in self.cum[k + 1:]]
            self.csum = [0.0] + [c - b2 for c in self.csum[k + 1:]]

    def rv(self, window):
        n = min(window, len(self.cum) - 1)
        if n < window // 2:
            return None
        return math.sqrt((self.cum[-1] - self.cum[-1 - n]) / n)

    def avg(self, lo, hi):
        """Mean of samples with lo <= sec < hi (None if fewer than 20)."""
        i, j = bisect.bisect_left(self.secs, lo), bisect.bisect_left(self.secs, hi)
        if j - i < 20:
            return None
        return (self.csum[j] - self.csum[i]) / (j - i)


class LateConfirmed(Strategy):
    params = {
        "z_thr": 1.5,                          # |previous-window move| in 15-minute sigmas
        "late_s": 300,                         # length of the late part of the previous window
        "late_thr": 1.5,                       # |late move| in late_s-sigmas, same sign as the window move
        "checkpoints": [870, 840, 810, 780],   # seconds before close; one entry per market at the first that fires
        "lo": 300, "hi": 700,                  # mid range (mills)
        "min_hist_s": 3600,
        "rv_scale": 1.0,                       # live multi-exchange median reads lower rv than Binance 1 s
        "max_k_jump": 0.02,
        "slip_c": 0,                           # IOC this many cents through the touch (paper: 1)
        "trade_series": "KXBTC15M",            # only this series is traded; others (if listed) feed spot only
        "basket": 0,                           # H2: 1 = also require the BTC/ETH/SOL basket move (mean z) to be late-confirmed
        "basket_series": ["KXBTC15M", "KXETH15M", "KXSOL15M"],
    }

    def on_start(self, ctx):
        self.hist: dict[str, _Hist] = {}
        self.strikes: dict[tuple[str, int], float] = {}
        self.done: set[str] = set()
        if ctx.spot_history:
            for series in ctx.spot_map:
                h = self.hist.setdefault(series, _Hist())
                for sec, px in ctx.spot_history(series, 4000):
                    h.add(sec, px)

    def _note(self, m):
        if m.strike is not None:
            self.strikes[(m.series, m.close_ts)] = m.strike

    def on_market(self, ctx, m):
        self._note(m)

    def on_timer(self, ctx):
        now_s = ctx.now // NS
        for series in ctx.spot_map:
            s = ctx.spot(series=series)
            if s is not None:
                self.hist.setdefault(series, _Hist()).add(now_s, s)
        for m in ctx.active_markets():
            if (m.series, m.close_ts) not in self.strikes:
                self._note(m)
            if m.ticker in self.done or m.series != self.p.trade_series:
                continue
            tau = int(round((m.close_ts - ctx.now) / NS))
            if tau < min(self.p.checkpoints):
                self.done.add(m.ticker)
                continue
            if tau in self.p.checkpoints:
                self._consider(ctx, m)

    def _consider(self, ctx, m):
        K, Kp = m.strike, self.strikes.get((m.series, m.open_ts))
        h = self.hist.get(m.series)
        if K is None or Kp is None or not h or h.secs[-1] - h.secs[0] < self.p.min_hist_s:
            return
        if abs(K / Kp - 1) > self.p.max_k_jump:
            return
        rv = h.rv(3600)
        if not rv:
            return
        rv *= self.p.rv_scale
        z = (K - Kp) / (rv * 30.0)
        op, L = m.open_ts // NS, int(self.p.late_s)
        a1, a0 = h.avg(op - 60, op), h.avg(op - L - 60, op - L)
        if a1 is None or a0 is None:
            return
        zl = (a1 - a0) / (rv * math.sqrt(L))
        ctx.record(m.ticker, "prev_z", z)
        ctx.record(m.ticker, "late_z", zl)
        if abs(z) <= self.p.z_thr or abs(zl) <= self.p.late_thr or (z > 0) != (zl > 0):
            self.done.add(m.ticker)  # the signal is fixed for the whole window
            return
        if self.p.basket:
            bz = self._basket(op, L)
            if bz is None:
                return
            B15, B5 = bz
            ctx.record(m.ticker, "basket_z15", B15)
            ctx.record(m.ticker, "basket_z5", B5)
            if abs(B15) <= self.p.z_thr or abs(B5) <= self.p.late_thr or (B15 > 0) != (z > 0) or (B5 > 0) != (z > 0):
                self.done.add(m.ticker)
                return
        book = ctx.book(m.ticker)
        if book is None or book.best_bid is None or book.best_ask is None or book.best_ask < book.best_bid:
            return
        mid = (book.best_bid + book.best_ask) / 2
        if not (self.p.lo <= mid <= self.p.hi):
            return
        if z < 0:
            side, px = Side.BUY, min(999, book.best_ask + 10 * self.p.slip_c)
        else:
            side, px = Side.SELL, max(1, book.best_bid - 10 * self.p.slip_c)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"z={z:+.2f} zl={zl:+.2f}")
            self.done.add(m.ticker)

    def _basket(self, op, L):
        """Mean over the basket coins of z15 and zL from 60 s spot averages (own rv_60m units)."""
        z15s, zls = [], []
        for series in self.p.basket_series:
            h = self.hist.get(series)
            if not h or not h.secs or h.secs[-1] - h.secs[0] < self.p.min_hist_s:
                return None
            rv = h.rv(3600)
            a1, a0, a15 = h.avg(op - 60, op), h.avg(op - L - 60, op - L), h.avg(op - 960, op - 900)
            if not rv or a1 is None or a0 is None or a15 is None:
                return None
            rv *= self.p.rv_scale
            z15s.append((a1 - a15) / (rv * 30.0))
            zls.append((a1 - a0) / (rv * math.sqrt(L)))
        return sum(z15s) / len(z15s), sum(zls) / len(zls)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.strikes = {k: v for k, v in self.strikes.items() if k[1] >= m.close_ts - 3600 * NS}
