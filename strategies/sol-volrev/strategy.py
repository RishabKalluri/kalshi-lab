"""SOL: fade the previous window's big move at the open, only when that window traded on heavy volume.

Research (strategies/sol-volrev/research/, dev data): the open-reversal edge after |z1| > 1.25 lives in windows whose Binance
volume was high relative to the same quarter-hour slot's 14-day median (relv > 2: +4.1c, > 3: +5.7c; low-volume moves +0..-1c).
Mechanism: a big move on heavy volume is forced flow (liquidations, stop runs) that unwinds; a big move on thin volume is
drift that persists. Base rule is eth-overreact's (derived_from). Backtests load backfill flow files per day; paper/live
would need a live Binance volume stream (the recorder doesn't stream flow yet).

Original eth-overreact docstring:
Fade the previous window's big move at the open of the next 15-minute window.

15-minute crypto returns have a small, persistent *sign* reversal (research/reversal_stats.py: sign autocorrelation
-0.02..-0.09 in every development month for BTC, ETH and SOL; after a |z| > 1.5 move the next window goes the other
way ~56% of the time). The Kalshi price in the first minutes of the next window sits near 50c regardless, pricing
only spot vs strike. So right after the open, when the previous window moved a lot, buy the reversal side.

  previous move  z = (K_this - K_prev) / (rv_60m * sqrt(900)). Each window's strike is the CF 60 s average before
                 its open, i.e. the previous window's settlement value, so K_this - K_prev is the previous window's
                 move in CF terms (no Binance-vs-CF basis error). rv_60m from 1 s spot.
  entry          at fixed checkpoints in the first 1.5 minutes (h = 870, 840, 810, 780 s before close), once per
                 market: if |z| > z_thr and the mid is within [lo, hi], buy YES at the ask if z < 0 (previous
                 window fell), else sell YES at the bid (buy NO). Hold to settlement.
Research (development data, next real fills, after fee): ETH |z| > 1.5 first trigger +4.8c Jan-Apr, +1.6c May-Aug.
"""

import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class _Hist:
    """1 s spot samples for the last ~1-2 h with a running sum of squared changes (from eth-volfav)."""
    KEEP = 3600 + 120

    def __init__(self):
        self.secs, self.px, self.cum = [], [], [0.0]

    def add(self, sec, price):
        if self.secs and sec <= self.secs[-1]:
            return
        if self.px:
            self.cum.append(self.cum[-1] + (price - self.px[-1]) ** 2)
        self.secs.append(sec)
        self.px.append(price)
        if len(self.secs) > 2 * self.KEEP:
            k = len(self.secs) - self.KEEP
            self.secs, self.px = self.secs[k:], self.px[k:]
            base = self.cum[k]
            self.cum = [0.0] + [c - base for c in self.cum[k + 1:]]

    def rv(self, window):
        n = min(window, len(self.cum) - 1)
        if n < window // 2:
            return None
        return math.sqrt((self.cum[-1] - self.cum[-1 - n]) / n)


class _SlotVol:
    """Binance spot volume per UTC quarter-hour slot, one day at a time (flow rows t in (slot start, slot end])."""

    def __init__(self, source):
        self.source, self.days = source, {}

    def day(self, d):
        if d not in self.days:
            import numpy as np
            import pandas as pd
            from kalshi_lab.data.flow import FLOW
            arr = np.full(96, np.nan)
            p = FLOW / self.source / f"{d.isoformat()}.parquet"
            if p.exists():
                f = pd.read_parquet(p, columns=["t", "buy", "sell"])
                base = int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp())
                slot = (f.t.to_numpy() - base - 1) // 900          # row t covers (t-1, t]: t=base+900 belongs to slot 0
                ok = (slot >= 0) & (slot < 96)
                arr = np.bincount(slot[ok], weights=(f.buy + f.sell).to_numpy()[ok], minlength=96)[:96]
                if arr.sum() == 0:
                    arr = np.full(96, np.nan)
            self.days[d] = arr
            for k in [k for k in self.days if (d - k).days > 20]:
                del self.days[k]
        return self.days[d]

    def relv(self, prev_open_s):
        """Volume in the window starting prev_open_s (unix s) relative to the 14-day median of the same slot."""
        import numpy as np
        t0 = datetime.fromtimestamp(prev_open_s, tz=timezone.utc)
        slot = (t0.hour * 3600 + t0.minute * 60) // 900
        cur = self.day(t0.date())[slot]
        hist = [self.day(t0.date() - timedelta(days=i))[slot] for i in range(1, 15)]
        hist = [x for x in hist if x == x and x > 0]
        if cur != cur or len(hist) < 7:
            return None
        return cur / float(np.median(hist))


class ReversalOpen(Strategy):
    params = {
        "z_thr": 1.25,                          # |previous-window move| in 15-minute sigmas
        "checkpoints": [870, 840, 810, 780],   # seconds before close; one entry per market at the first that fires
        "lo": 300, "hi": 700,                  # mid range (mills): only near-coin-flip prices
        "relv_thr": 2.0,                       # prior-window Binance volume / 14-day median of the same slot
        "min_hist_s": 3600,                    # spot history needed for rv_60m
        "rv_scale": 1.0,                       # live multi-exchange median reads ~8% lower rv than Binance 1 s
        "max_k_jump": 0.02,                    # skip if strikes look broken (|K/K_prev - 1| above this)
        "slip_c": 0,                           # IOC this many cents through the touch (paper: 1)
    }

    def on_start(self, ctx):
        self.hist: dict[str, _Hist] = {}
        self.strikes: dict[tuple[str, int], float] = {}   # (series, close_ts) -> strike
        self.done: set[str] = set()
        self.vols: dict[str, _SlotVol] = {}
        if ctx.spot_history:
            for series in ctx.spot_map:
                h = self.hist.setdefault(series, _Hist())
                for sec, px in ctx.spot_history(series, 3700):
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
        if K is None or Kp is None or not h or h.secs[-1] - h.secs[0] < self.p.min_hist_s:
            return
        if abs(K / Kp - 1) > self.p.max_k_jump:
            return
        rv = h.rv(3600)
        if not rv:
            return
        z = (K - Kp) / (rv * self.p.rv_scale * 30.0)
        ctx.record(m.ticker, "prev_z", z)
        if abs(z) <= self.p.z_thr:
            self.done.add(m.ticker)  # the signal is fixed for the whole window
            return
        sv = self.vols.get(m.series)
        if sv is None:
            from kalshi_lab.data.flow import flow_sources
            sv = self.vols[m.series] = _SlotVol(flow_sources(m.series)["binance"])
        rv_ = sv.relv(m.open_ts // NS - 900)
        ctx.record(m.ticker, "relv", rv_ if rv_ is not None else float("nan"))
        if rv_ is None or rv_ < self.p.relv_thr:
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
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"z={z:+.2f}")
            self.done.add(m.ticker)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.strikes = {k: v for k, v in self.strikes.items() if k[1] >= m.close_ts - 3600 * NS}
