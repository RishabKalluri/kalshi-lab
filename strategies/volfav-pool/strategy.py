"""VolFavorite pooled over BTC/ETH/SOL/XRP/DOGE 15-minute markets.

eth-volfav's mechanics (implied vol from the market price vs a HAR forecast from trailing realized vol; buy the
favourite late in the window when implied/forecast is high), with one pre-registered rule for all five coins:
  - the HAR forecast is fit per coin, refit monthly on earlier data (vol_fit.py);
  - the entry bar is the same *percentile* of each coin's own training ratios: top 15% on weekdays, top 40% on
    weekends (UTC close day), chosen from development-data research (weekends carry about 2x the edge per trade).
Checkpoints, spot basis, IOC at the touch are unchanged from eth-volfav2.
"""

import json
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from statistics import NormalDist

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
PARAMS = Path(__file__).parent / "params"
_inv = NormalDist().inv_cdf


class _Hist:
    """1s spot samples for the last ~4h with a running sum of squared changes (gap-safe, see eth-volfav2)."""
    KEEP = 4 * 3600 + 120

    def __init__(self):
        self.secs, self.px, self.cum = [], [], [0.0]

    def add(self, sec, price):
        if self.px:
            gap = max(1, sec - self.secs[-1])
            self.cum.append(self.cum[-1] + (price - self.px[-1]) ** 2 / gap)
        self.secs.append(sec)
        self.px.append(price)
        if len(self.secs) > 2 * self.KEEP:
            k = len(self.secs) - self.KEEP
            self.secs, self.px = self.secs[k:], self.px[k:]
            base = self.cum[k]
            self.cum = [0.0] + [c - base for c in self.cum[k + 1:]]

    def window(self, a, b):
        import bisect
        i, j = bisect.bisect_left(self.secs, a), bisect.bisect_left(self.secs, b)
        return self.px[i:j]


class PooledVolFavorite(Strategy):
    @classmethod
    def fit(cls, series: list[str], until: str | None) -> dict:
        from vol_fit import fit_all
        return {"model_tag": fit_all(series, until, cls.params["pct_weekend"], cls.params["pct_weekday"])}

    params = {
        "model_tag": "",       # set by fit(): vol_model_<SERIES><tag>.json
        "pct_weekend": 0.60,   # entry bar = this quantile of the coin's training ratios (Sat/Sun, UTC close day)
        "pct_weekday": 0.85,   # same, Mon-Fri
        "min_tau": 60,
        "max_tau": 360,
        "max_entries": 7,
        "min_hist_s": 3600,
        "rv_scale": 1.0,
        "checkpoints": [360, 300, 240, 180, 120, 90, 60],
        "slip_c": 0,
    }

    def on_start(self, ctx):
        self.hist: dict[str, _Hist] = {}
        self.models: dict[str, dict | None] = {}
        self.basis: dict[str, float] = {}
        self.entries: dict[str, list[int]] = {}
        if ctx.spot_history:
            for series in ctx.spot_map:
                h = self.hist.setdefault(series, _Hist())
                for sec, px in ctx.spot_history(series, 4 * 3600):
                    h.add(sec, px)

    def _model(self, series):
        if series not in self.models:
            path = PARAMS / f"vol_model_{series}{self.p.model_tag}.json"
            self.models[series] = json.loads(path.read_text()) if path.exists() else None
        return self.models[series]

    def _rv(self, h: _Hist, window: int) -> float | None:
        n = min(window, len(h.cum) - 1)
        if n < min(window, 300) // 2:
            return None
        return math.sqrt((h.cum[-1] - h.cum[-1 - n]) / n)

    def on_timer(self, ctx):
        now_s = ctx.now // NS
        for series in ctx.spot_map:
            s = ctx.spot(series=series)
            if s is None:
                continue
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
        tau = (m.close_ts - ctx.now) / NS
        if not (self.p.min_tau <= tau <= self.p.max_tau) or m.ticker not in self.basis:
            return
        if self.p.checkpoints and int(round(tau)) not in self.p.checkpoints:
            return
        ent = self.entries.setdefault(m.ticker, [])
        if len(ent) >= self.p.max_entries:
            return
        md = self._model(m.series)
        if md is None:
            return
        h = self.hist.get(m.series)
        book = ctx.book(m.ticker)
        if not h or book is None or book.best_bid is None or book.best_ask is None:
            return
        if h.secs[-1] - h.secs[0] < self.p.min_hist_s:
            return
        rv15, rv60 = self._rv(h, 900), self._rv(h, 3600)
        rv4h = self._rv(h, 14400) or rv60
        if not (rv15 and rv60 and rv4h):
            return
        rv15, rv60, rv4h = (x * self.p.rv_scale for x in (rv15, rv60, rv4h))
        mid = (book.best_bid + book.best_ask) / 2000
        if not (0.03 < mid < 0.97 and abs(mid - 0.5) > 0.07):
            return
        D = h.px[-1] + self.basis[m.ticker] - m.strike
        z = _inv(mid)
        if z * D <= 0:
            return
        iv = D / (z * math.sqrt(tau - 40))
        close_s = m.close_ts // NS
        weekend = datetime.fromtimestamp(close_s, timezone.utc).weekday() >= 5
        hour = (close_s // 3600) % 24
        x = [1.0, math.log(rv15), math.log(rv60), math.log(rv4h)] + [1.0 if hour == hh else 0.0 for hh in range(1, 24)] + [math.log(tau)]
        fc = math.exp(sum(b * v for b, v in zip(md["beta"], x)))
        ratio = iv / fc
        ctx.record(m.ticker, "ratio", ratio)
        if ratio <= md["thr_weekend" if weekend else "thr_weekday"]:
            return
        if mid > 0.5:
            side, px = Side.BUY, book.best_ask
        else:
            side, px = Side.SELL, book.best_bid
        px = min(999, px + 10 * self.p.slip_c) if side == Side.BUY else max(1, px - 10 * self.p.slip_c)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"r={ratio:.2f}")
            ent.append(now_s)

    def on_settle(self, ctx, m, pnl):
        self.basis.pop(m.ticker, None)
        self.entries.pop(m.ticker, None)
