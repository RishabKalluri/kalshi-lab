"""Weekend open reversal: fade the previous window's big move at the open, on Saturdays and Sundays (UTC), pooled over five coins.

Screen (dev data, next real fills after fee, |z15|>1.25, mid 25-75c, h=840): weekend minus weekday reversal edge is positive
on all five coins in both Jan-Apr and May-Aug (thin weekend books, retail-dominated): SOL +2.4/+1.8c, ETH +2.4/+1.4, BTC +9.0/+2.0,
XRP +4.8/+1.2, DOGE +4.5. Weekdays have decayed to ~0 after May; weekends kept +0.3..+6.5c. Signal = sol-midrev's z15 without the late filter.
"""

import bisect
from datetime import datetime, timezone
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


class WeekendRev(Strategy):
    params = {
        "z_thr": 1.25,                         # |previous-window move| in 15-minute sigmas
        "weekend_only": 1,                     # trade only windows opening Saturday/Sunday UTC
        "late_thr": 0.0,                       # optional: |late move of the previous window| in late_s-sigmas, same sign
        "late_s": 300,
        "checkpoints": [870, 840, 810, 780],  # seconds before close; one entry per market at the first that fires
        "lo": 250, "hi": 750,                  # mid range (mills)
        "min_hist_s": 3600,
        "rv_scale": 1.0,                       # live multi-exchange median reads lower rv than Binance 1 s
        "max_k_jump": 0.02,
        "slip_c": 0,                           # IOC this many cents through the touch (paper: 1)
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
            if m.ticker in self.done:
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
        if self.p.weekend_only and datetime.fromtimestamp(m.open_ts // NS, timezone.utc).weekday() < 5:
            self.done.add(m.ticker)
            return
        if K is None or Kp is None or not h or h.secs[-1] - h.secs[0] < self.p.min_hist_s:
            return
        if abs(K / Kp - 1) > self.p.max_k_jump:
            return
        rv = h.rv(3600)
        if not rv:
            return
        rv *= self.p.rv_scale
        z = (K - Kp) / (rv * 30.0)
        zl = 0.0
        if self.p.late_thr > 0:
            op, L = m.open_ts // NS, int(self.p.late_s)
            a1, a0 = h.avg(op - 60, op), h.avg(op - L - 60, op - L)
            if a1 is None or a0 is None:
                return
            zl = (a1 - a0) / (rv * math.sqrt(L))
        ctx.record(m.ticker, "prev_z", z)
        if abs(z) <= self.p.z_thr or (self.p.late_thr > 0 and (abs(zl) <= self.p.late_thr or (z > 0) != (zl > 0))):
            self.done.add(m.ticker)  # the signal is fixed for the whole window
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

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.strikes = {k: v for k, v in self.strikes.items() if k[1] >= m.close_ts - 3600 * NS}
