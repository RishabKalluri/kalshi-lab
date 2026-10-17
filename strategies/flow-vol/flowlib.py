"""Order-flow features for the vol forecast, shared by fit() (vectorized over the dataset) and the strategy (one
decision time at a time). Flow row t covers trades in (t-1, t]; a decision at second T uses rows t in [T-w, T-1].

Features (per coin, Binance spot + OKX perp together): log volume/s and log trades/s over 1m/5m/15m/60m (lv_*, ln_*),
log of the largest OKX single trade in the last 60/300 s (lmx_*), perp share of volume (perp_*), |net taker
imbalance| and signed imbalance (aimb_*, simb_*).
"""

import math
from datetime import date, datetime, timedelta, timezone

import numpy as np
import pandas as pd

from kalshi_lab.data.flow import FLOW, flow_sources

EPS = 1e-9
WINDOWS = [(60, "1m"), (300, "5m"), (900, "15m"), (3600, "60m")]
FEATURES = (["lv_1m", "lv_5m", "lv_15m", "lv_60m", "ln_1m", "ln_5m", "ln_15m", "ln_60m", "lmx_60", "lmx_300",
             "perp_5m", "perp_15m", "aimb_5m", "aimb_15m", "simb_5m"])


def _day_arrays(source: str, day: date):
    """Dense per-second arrays for one UTC day: buy, sell, n, max_trade (zeros where no trades)."""
    cols = {k: np.zeros(86400) for k in ("buy", "sell", "n", "mx")}
    p = FLOW / source / f"{day.isoformat()}.parquet"
    if p.exists():
        f = pd.read_parquet(p)
        i = f.t.to_numpy() - int(datetime(day.year, day.month, day.day, tzinfo=timezone.utc).timestamp())
        ok = (i >= 0) & (i < 86400)
        i = i[ok]
        cols["buy"][i] = f.buy.to_numpy()[ok]
        cols["sell"][i] = f.sell.to_numpy()[ok]
        cols["n"][i] = f.n.to_numpy()[ok]
        if "max_trade" in f:
            cols["mx"][i] = f.max_trade.fillna(0).to_numpy()[ok]
    return cols


def build_feats(series: str, d: pd.DataFrame, until=None) -> pd.DataFrame:
    """Vectorized features for dataset rows (columns close, h) at decision time close - h. `until`: skip flow days >= it."""
    src = flow_sources(series)
    T = d.close.values.astype("datetime64[s]").astype(np.int64) - d.h.to_numpy()
    T0 = int(T.min()) - 4000
    T0 -= T0 % 86400
    N = int(T.max()) + 1 - T0 + 1
    arrs = {}
    for ex, source in (("bn", src["binance"]), ("ok", src["okx"])):
        cols = {k: np.zeros(N) for k in ("buy", "sell", "n", "mx")}
        day = datetime.fromtimestamp(T0, tz=timezone.utc).date()
        while (day - date(1970, 1, 1)).days * 86400 < T0 + N:
            if until is None or day < until:
                a = _day_arrays(source, day)
                s = (day - date(1970, 1, 1)).days * 86400 - T0
                for k in cols:
                    cols[k][max(s, 0):s + 86400] = a[k][max(-s, 0):N - s]
            day += timedelta(days=1)
        arrs[ex] = cols
    cs = lambda a: np.concatenate([[0.0], np.cumsum(a)])
    C = {f"{ex}_{k}": cs(v) for ex, c in arrs.items() for k, v in c.items() if k != "mx"}
    mx = pd.Series(arrs["ok"]["mx"])
    MX = {w: mx.rolling(w, min_periods=1).max().to_numpy() for w in (60, 300)}
    i = T - 1 - T0
    W = lambda key, w: C[key][np.clip(i + 1, 0, N)] - C[key][np.clip(i - w + 1, 0, N)]
    out = {}
    for w, tag in WINDOWS:
        v_bn = W("bn_buy", w) + W("bn_sell", w)
        v_ok = W("ok_buy", w) + W("ok_sell", w)
        out[f"lv_{tag}"] = np.log((v_bn + v_ok) / w + EPS)
        out[f"ln_{tag}"] = np.log((W("bn_n", w) + W("ok_n", w)) / w + EPS)
        if w in (300, 900):
            s = W("bn_buy", w) - W("bn_sell", w) + W("ok_buy", w) - W("ok_sell", w)
            out[f"perp_{tag}"] = v_ok / (v_ok + v_bn + EPS)
            out[f"aimb_{tag}"] = np.abs(s) / (v_bn + v_ok + EPS)
            if w == 300:
                out[f"simb_{tag}"] = s / (v_bn + v_ok + EPS)
    for w in (60, 300):
        out[f"lmx_{w}"] = np.log(MX[w][i] + EPS)
    return pd.DataFrame(out, index=d.index)[FEATURES]


class FlowStore:
    """Strategy-side: incremental per-day arrays; features at one decision second."""

    def __init__(self, series: str):
        src = flow_sources(series)
        self.src = {"bn": src["binance"], "ok": src["okx"]}
        self.days: dict[date, dict] = {}

    def _day(self, day: date):
        if day not in self.days:
            if len(self.days) > 3:
                self.days.pop(min(self.days))
            self.days[day] = {ex: _day_arrays(s, day) for ex, s in self.src.items()}
        return self.days[day]

    def _slice(self, ex: str, key: str, a: int, b: int) -> np.ndarray:
        """Seconds [a, b) of array `key` (unix seconds), across at most two days."""
        parts = []
        while a < b:
            day = datetime.fromtimestamp(a, tz=timezone.utc).date()
            base = (day - date(1970, 1, 1)).days * 86400
            e = min(b, base + 86400)
            parts.append(self._day(day)[ex][key][a - base:e - base])
            a = e
        return np.concatenate(parts)

    def feats(self, T: int) -> dict:
        out = {}
        sl = lambda ex, key, w: self._slice(ex, key, T - w, T)
        for w, tag in WINDOWS:
            v_bn = sl("bn", "buy", w).sum() + sl("bn", "sell", w).sum()
            v_ok = sl("ok", "buy", w).sum() + sl("ok", "sell", w).sum()
            out[f"lv_{tag}"] = math.log((v_bn + v_ok) / w + EPS)
            out[f"ln_{tag}"] = math.log((sl("bn", "n", w).sum() + sl("ok", "n", w).sum()) / w + EPS)
            if w in (300, 900):
                s = sl("bn", "buy", w).sum() - sl("bn", "sell", w).sum() + sl("ok", "buy", w).sum() - sl("ok", "sell", w).sum()
                out[f"perp_{tag}"] = v_ok / (v_ok + v_bn + EPS)
                out[f"aimb_{tag}"] = abs(s) / (v_bn + v_ok + EPS)
                if w == 300:
                    out[f"simb_{tag}"] = s / (v_bn + v_ok + EPS)
        for w in (60, 300):
            out[f"lmx_{w}"] = math.log(float(sl("ok", "mx", w).max()) + EPS)
        return out
