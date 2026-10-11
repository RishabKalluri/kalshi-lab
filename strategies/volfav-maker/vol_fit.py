"""Fit the VolFavorite vol forecast + entry threshold on data before a cutoff (the strategy's fit() hook).

Copied unchanged from strategies/eth-volfav/vol_fit.py (same model, same 70th-percentile threshold) so the signal
is identical to eth-volfav's; only the execution differs. Writes into this folder's params/.

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
    thr = float((d.iv / np.exp(X(d) @ beta)).quantile(pct))
    tag = "" if cutoff is None else "_until_" + cutoff.strftime("%Y%m%dT%H%M")
    name = f"vol_model_{series}{tag}.json"
    PARAMS.mkdir(exist_ok=True)
    (PARAMS / name).write_text(json.dumps({
        "series": series, "fit_until": str(cutoff or df.close.max()), "n_markets": int(df.ticker.nunique()),
        "beta": [float(x) for x in beta], "ratio_threshold": thr, "ratio_pct": pct,
        "features": "1, log rv_15m, log rv_60m, log rv_4h, hour==1..23 (UTC close hour), log h"}, indent=1))
    return name
