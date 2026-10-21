"""Fit VolFavorite's vol forecast + entry threshold on data before a cutoff (the strategy's fit() hook).

log rv_fut = beta . [1, log rv_15m, log rv_60m, log rv_4h, UTC-hour dummies, log h]; the entry threshold is
the `pct` quantile of implied/forecast vol at the trading horizons. Uses research/data/<SERIES>.parquet
(built by research/build_dataset.py from the backfill; rebuilt automatically when stale).
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]  # repo root (this file is strategies/<slug>/vol_fit.py)
PARAMS = Path(__file__).parent / "params"
H = [360, 300, 240, 180, 120, 90, 60]


def _dataset(series: str, need_until: pd.Timestamp) -> pd.DataFrame:
    """Development data (before the lockbox) unless the fit needs later data (paper/live refits)."""
    from kalshi_lab.validate import LOCKBOX_START
    full = need_until > pd.Timestamp(LOCKBOX_START)
    path = ROOT / "research" / "data" / f"{series}{'_all' if full else ''}.parquet"
    target = need_until if full else pd.Timestamp(LOCKBOX_START)
    if path.exists():
        df = pd.read_parquet(path)
        if df.close.max() >= target - pd.Timedelta(days=2):
            return df
    cmd = [sys.executable, str(ROOT / "research" / "build_dataset.py"), series] + (["--include-lockbox"] if full else [])
    subprocess.check_call(cmd, cwd=ROOT)
    return pd.read_parquet(path)


def fit_model(series: str, until=None, pct: float = 0.7) -> str:
    """Fit on markets closing before `until` (ISO string or None = all); returns the params file name."""
    cutoff = pd.Timestamp(until, tz="UTC") if until else None
    df = _dataset(series, cutoff or pd.Timestamp.now(tz="UTC"))
    if cutoff is not None:
        df = df[df.close < cutoff]
    df = df.dropna(subset=["rv_15m", "rv_60m", "rv_4h"])
    df = df[(df.rv_15m > 0) & (df.rv_60m > 0) & (df.rv_4h > 0)].copy()
    df["hour"] = df.close.dt.hour
    X = lambda d: np.column_stack([np.ones(len(d)), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
                                   *[(d.hour == hh).astype(float) for hh in range(1, 24)], np.log(d.h)])
    fit = df[df.rv_fut > 0.05]
    beta, *_ = np.linalg.lstsq(X(fit), np.log(fit.rv_fut), rcond=None)
    d = df.dropna(subset=["iv"])
    d = d[d.h.isin(H)]
    ratio = d.iv / np.exp(X(d) @ beta)
    thr = float(ratio.quantile(pct))
    # Calibration for Kelly sizing: at signals, how much of the model's claimed edge over the market shows up in
    # outcomes. Model P(favourite) = Phi(|Phi^-1(mid)| * ratio); k = slope of (won - market prob) on (model prob -
    # market prob) through 0, clipped to [0, 1]. Measured OUT of sample: forecast and threshold fit on the first 70% of
    # the training period, k on the last 30% (in-sample k is ~0.85-0.95 because the forecast has seen those markets;
    # out of sample on Mar-Aug it is ~0.35).
    from scipy.stats import norm
    cut = df.close.quantile(0.7)
    fa = fit[fit.close < cut]
    ba, *_ = np.linalg.lstsq(X(fa), np.log(fa.rv_fut), rcond=None)
    da, db = d[d.close < cut], d[d.close >= cut]
    thr_a = float((da.iv / np.exp(X(da) @ ba)).quantile(pct))
    r_b = db.iv / np.exp(X(db) @ ba)
    s = db[(r_b > thr_a) & (db.mid - 0.5).abs().gt(0.07) & db.mid.between(0.03, 0.97) & db.y.notna()]
    rr = r_b[s.index]
    pm = np.where(s.mid > 0.5, s.mid, 1 - s.mid)
    pmod = norm.cdf(np.abs(norm.ppf(s.mid)) * rr)
    won = np.where(s.mid > 0.5, s.y, 1 - s.y)
    x, yv = pmod - pm, won - pm
    shrink = float(np.clip((x * yv).sum() / (x * x).sum(), 0, 1)) if len(s) > 200 else 0.0
    tag = "" if cutoff is None else "_until_" + cutoff.strftime("%Y%m%dT%H%M")
    name = f"vol_model_{series}{tag}.json"
    PARAMS.mkdir(exist_ok=True)
    (PARAMS / name).write_text(json.dumps({
        "series": series, "fit_until": str(cutoff or df.close.max()), "n_markets": int(df.ticker.nunique()),
        "beta": [float(x) for x in beta], "ratio_threshold": thr, "ratio_pct": pct, "edge_shrink": shrink,
        "n_signals_calibration": int(len(s)),
        "features": "1, log rv_15m, log rv_60m, log rv_4h, hour==1..23 (UTC close hour), log h"}, indent=1))
    return name
