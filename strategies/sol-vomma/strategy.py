"""SOL Vomma: buy the favourite on KXSOL15M when the market's implied vol is high relative to a vol forecast.

Started as a vol-of-vol ("vomma") pricing idea: price the binary as a mixture over an uncertain future vol.
Research (research/market_vomma.py, model_vs_fill.py) showed the vomma correction is < 1c, smaller than the
fee + spread, and adds nothing over a point-vol model. What survived screening (research/ratio_deciles.py)
is the vol *level* error: when implied vol / forecast vol is in the top 30%, the favourite's next real fill
earned about +1c/contract after fees in both halves of development data. So this is the eth-volfav method,
ported to SOL (code reused from strategies/eth-volfav/).

  implied vol   iv = D / (Phi^-1(mid) * sqrt(tau - 40)),  D = spot + basis - strike, basis = strike -
                our 60s average before open (the strike is the index's 60s average before open)
  forecast      log rv = beta . [1, log rv15m, log rv60m, log rv4h, hour dummies, log tau]  (fit() refits it
                before every walk-forward month on earlier data only; params/ holds the fits)
  entry         at fixed checkpoints, ratio = iv / forecast > threshold -> buy the favourite at the ask (IOC)
"""

import bisect
import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
PARAMS = Path(__file__).parent / "params"
_inv = NormalDist().inv_cdf


class _Hist:
    """1s spot samples for the last ~4h with a running sum of squared changes."""
    KEEP = 4 * 3600 + 120

    def __init__(self):
        self.secs, self.px, self.cum = [], [], [0.0]

    def add(self, sec, price):
        if self.px:
            self.cum.append(self.cum[-1] + (price - self.px[-1]) ** 2)
        self.secs.append(sec)
        self.px.append(price)
        if len(self.secs) > 2 * self.KEEP:  # trim in chunks so appends stay O(1) amortized
            k = len(self.secs) - self.KEEP
            self.secs, self.px = self.secs[k:], self.px[k:]
            base = self.cum[k]
            self.cum = [0.0] + [c - base for c in self.cum[k + 1:]]

    def window(self, a, b):
        i, j = bisect.bisect_left(self.secs, a), bisect.bisect_left(self.secs, b)
        return self.px[i:j]


class SolVomma(Strategy):
    @classmethod
    def fit(cls, series: list[str], until: str | None) -> dict:
        """Pipeline hook: fit the vol model on data before `until`; returns param overrides."""
        from vol_fit import fit_model
        return {"model": fit_model(series[0], until, pct=0.7)}

    params = {
        "model": "",           # params file name; default vol_model_<SERIES>.json
        "min_tau": 60,
        "max_tau": 360,
        "max_entries": 7,
        "threshold_mult": 1.0,
        "min_hist_s": 3600,
        "rv_scale": 1.0,       # live multi-exchange median reads lower rv than Binance 1s; 1.0 in backfill
        "checkpoints": [360, 300, 240, 180, 120, 90, 60],
    }

    def on_start(self, ctx):
        self.hist = {}
        self.models = {}
        self.basis = {}
        self.entries = {}
        if ctx.spot_history:
            for series in ctx.spot_map:
                pts = ctx.spot_history(series, 4 * 3600)
                h = self.hist.setdefault(series, _Hist())
                for sec, px in pts:
                    h.add(sec, px)

    def _model(self, series):
        if series not in self.models:
            name = self.p.model or f"vol_model_{series}.json"
            self.models[series] = json.loads((PARAMS / name).read_text())
        return self.models[series]

    def _rv(self, h, window):
        n = min(window, len(h.cum) - 1)
        if n < min(window, 300) // 2:
            return None
        return math.sqrt((h.cum[-1] - h.cum[-1 - n]) / n)

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
        tau = (m.close_ts - ctx.now) / NS
        if not (self.p.min_tau <= tau <= self.p.max_tau) or m.ticker not in self.basis:
            return
        if self.p.checkpoints and int(round(tau)) not in self.p.checkpoints:
            return
        ent = self.entries.setdefault(m.ticker, [])
        if len(ent) >= self.p.max_entries:
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
        md = self._model(m.series)
        hour = (m.close_ts // NS // 3600) % 24
        x = [1.0, math.log(rv15), math.log(rv60), math.log(rv4h)] + [1.0 if hour == hh else 0.0 for hh in range(1, 24)] + [math.log(tau)]
        fc = math.exp(sum(b * v for b, v in zip(md["beta"], x)))
        ratio = iv / fc
        ctx.record(m.ticker, "ratio", ratio)
        if ratio <= md["ratio_threshold"] * self.p.threshold_mult:
            return
        side, px = (Side.BUY, book.best_ask) if mid > 0.5 else (Side.SELL, book.best_bid)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"r={ratio:.2f}")
            ent.append(now_s)

    def on_settle(self, ctx, m, pnl):
        self.basis.pop(m.ticker, None)
        self.entries.pop(m.ticker, None)
