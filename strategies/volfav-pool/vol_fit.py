"""Pooled VolFavorite fit: per coin, a HAR vol forecast + two entry thresholds (weekend / weekday), on data before a cutoff.

log rv_fut = beta . [1, log rv_15m, log rv_60m, log rv_4h, UTC-hour dummies, log h]. The thresholds are quantiles of
implied/forecast vol over the training rows at the trading horizons (the same percentile for every coin, which is what
pools them). Uses research/data/<SERIES>.parquet (built by research/build_dataset.py; rebuilt automatically when stale).
A coin with fewer than MIN_MARKETS training markets gets no file and is not traded that month.
"""

import json
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PARAMS = Path(__file__).parent / "params"
H = [360, 300, 240, 180, 120, 90, 60]
MIN_MARKETS = 800


def _dataset(series: str) -> pd.DataFrame:
    from kalshi_lab.validate import LOCKBOX_START
    path = ROOT / "research" / "data" / f"{series}.parquet"
    if path.exists():
        df = pd.read_parquet(path)
        if df.close.max() >= pd.Timestamp(LOCKBOX_START) - pd.Timedelta(days=2):
            return df
    subprocess.check_call([sys.executable, str(ROOT / "research" / "build_dataset.py"), series], cwd=ROOT)
    return pd.read_parquet(path)


def _x(d):
    return np.column_stack([np.ones(len(d)), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
                            *[(d.close.dt.hour == hh).astype(float) for hh in range(1, 24)], np.log(d.h)])


def fit_all(series: list[str], until: str, pct_weekend: float, pct_weekday: float) -> str:
    """Fit every series on markets closing before `until`; returns the file tag (_until_YYYYMMDDTHHMM)."""
    cutoff = pd.Timestamp(until, tz="UTC")
    tag = "_until_" + cutoff.strftime("%Y%m%dT%H%M")
    PARAMS.mkdir(exist_ok=True)
    for s in series:
        df = _dataset(s)
        df = df[df.close < cutoff].dropna(subset=["rv_15m", "rv_60m", "rv_4h"])
        df = df[(df.rv_15m > 0) & (df.rv_60m > 0) & (df.rv_4h > 0)]
        if df.ticker.nunique() < MIN_MARKETS:
            continue
        fit = df[df.rv_fut > 2e-5 * df.S]  # relative to price so it works for any coin
        beta, *_ = np.linalg.lstsq(_x(fit), np.log(fit.rv_fut), rcond=None)
        d = df.dropna(subset=["iv"])
        d = d[d.h.isin(H)]
        ratio = d.iv / np.exp(_x(d) @ beta)
        (PARAMS / f"vol_model_{s}{tag}.json").write_text(json.dumps({
            "series": s, "fit_until": str(cutoff), "n_markets": int(df.ticker.nunique()),
            "beta": [float(x) for x in beta],
            "thr_weekend": float(ratio.quantile(pct_weekend)), "thr_weekday": float(ratio.quantile(pct_weekday)),
            "pct_weekend": pct_weekend, "pct_weekday": pct_weekday}, indent=1))
    return tag
