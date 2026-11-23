"""Open-reversal ridge score pooled over BTC/ETH/SOL: one fitted score instead of hand-set z/volume thresholds.

After a window opens, the previous window's move (z), its late confirmation (zl: the last 5 minutes ran the same way),
Binance volume relative to the same slot's 14-day median (relv) and the clock are combined by a ridge regression
(fit() before each month on earlier windows only; target = net PnL of fading the move at the first-minute fill). Buy the
reversal side when the predicted net PnL exceeds `thr`. Combines the signals of sol-midrev (late confirmation) and
sol-volrev (volume) and eth-overreact (size of the move). Backtests load backfill flow per day (paper/live would need a
live Binance volume stream).
"""

import bisect
import json
import math
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
PARAMS = Path(__file__).parent / "params"


class _Hist:
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
        i, j = bisect.bisect_left(self.secs, lo), bisect.bisect_left(self.secs, hi)
        if j - i < 20:
            return None
        return (self.csum[j] - self.csum[i]) / (j - i)


class _SlotVol:
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
                slot = (f.t.to_numpy() - base - 1) // 900
                ok = (slot >= 0) & (slot < 96)
                arr = np.bincount(slot[ok], weights=(f.buy + f.sell).to_numpy()[ok], minlength=96)[:96]
                if arr.sum() == 0:
                    arr = np.full(96, np.nan)
            self.days[d] = arr
            for k in [k for k in self.days if (d - k).days > 20]:
                del self.days[k]
        return self.days[d]

    def relv(self, prev_open_s):
        import numpy as np
        t0 = datetime.fromtimestamp(prev_open_s, tz=timezone.utc)
        slot = (t0.hour * 3600 + t0.minute * 60) // 900
        cur = self.day(t0.date())[slot]
        hist = [self.day(t0.date() - timedelta(days=i))[slot] for i in range(1, 15)]
        hist = [x for x in hist if x == x and x > 0]
        if cur != cur or cur <= 0 or len(hist) < 7:
            return None
        return cur / float(np.median(hist))


class RevPool(Strategy):
    @classmethod
    def fit(cls, series: list[str], until: str | None) -> dict:
        from rev_fit import fit_model
        return {"model": fit_model(series, until)}

    params = {
        "model": "",
        "thr": 0.06,                           # predicted net PnL per contract (prob units) needed to trade
        "checkpoints": [870, 840, 810, 780],
        "lo": 250, "hi": 750,
        "min_hist_s": 3600,
        "rv_scale": 1.0,
        "max_k_jump": 0.02,
        "slip_c": 0,
    }

    def on_start(self, ctx):
        self.hist: dict[str, _Hist] = {}
        self.strikes: dict[tuple[str, int], float] = {}
        self.done: set[str] = set()
        self.vols: dict[str, _SlotVol] = {}
        self.models: dict[str, dict] = {}
        if ctx.spot_history:
            for series in ctx.spot_map:
                h = self.hist.setdefault(series, _Hist())
                for sec, px in ctx.spot_history(series, 4000):
                    h.add(sec, px)

    def _model(self, series):
        name = self.p.model
        if name not in self.models:
            self.models[name] = json.loads((PARAMS / name).read_text())
        return self.models[name]

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
        import numpy as np
        import pandas as pd
        from rev_fit import design, features
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
        op = m.open_ts // NS
        a1, a0 = h.avg(op - 60, op), h.avg(op - 360, op - 300)
        if a1 is None or a0 is None:
            return
        zl = (a1 - a0) / (rv * math.sqrt(300))
        sv = self.vols.get(m.series)
        if sv is None:
            from kalshi_lab.data.flow import flow_sources
            sv = self.vols[m.series] = _SlotVol(flow_sources(m.series)["binance"])
        rel = sv.relv(op - 900)
        if rel is None:
            self.done.add(m.ticker)
            return
        mod = self._model(m.series)
        close = pd.Timestamp(m.close_ts, unit="ns", tz="UTC")
        ft = features(np.array([z]), np.array([zl]), np.array([rel]), close)
        pred = float(np.dot(design(ft)[0], mod["coef"]) + mod["intercept"])
        ctx.record(m.ticker, "pred", pred)
        if pred <= self.p.thr:
            self.done.add(m.ticker)  # signal is fixed for the whole window
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
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC,
                                                         tag=f"z={z:+.2f} zl={zl:+.2f} rv={rel:.1f} p={pred:+.3f}")
            self.done.add(m.ticker)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.strikes = {k: v for k, v in self.strikes.items() if k[1] >= m.close_ts - 3600 * NS}
