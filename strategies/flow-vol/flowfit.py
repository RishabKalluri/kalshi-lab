"""Fit FlowVol's vol forecast + entry threshold on data before a cutoff (the strategy's fit() hook).

log rv_fut = beta . [1, log rv_15m, log rv_60m, log rv_4h, UTC-hour dummies, log h, log rv_5m, flow features];
threshold = the `pct` quantile of implied/forecast vol at the trading horizons. Dataset from research/build_dataset.py,
flow features from flowlib.build_feats (cached in params/).
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
sys.path.insert(0, str(Path(__file__).parent))
from flowlib import FEATURES, build_feats  # noqa: E402


def _dataset(series: str, need_until: pd.Timestamp) -> pd.DataFrame:
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


def design(d: pd.DataFrame):
    hour = d.close.dt.hour
    return np.column_stack([np.ones(len(d)), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
                            *[(hour == hh).astype(float) for hh in range(1, 24)], np.log(d.h), np.log(d.rv_5m),
                            *[d[c].to_numpy() for c in FEATURES]])


def fit_model(series: str, until=None, pct: float = 0.8) -> str:
    cutoff = pd.Timestamp(until, tz="UTC") if until else None
    df = _dataset(series, cutoff or pd.Timestamp.now(tz="UTC"))
    if cutoff is not None:
        df = df[df.close < cutoff]
    df = df.dropna(subset=["rv_5m", "rv_15m", "rv_60m", "rv_4h"])
    df = df[(df.rv_5m > 0) & (df.rv_15m > 0) & (df.rv_60m > 0) & (df.rv_4h > 0)].copy()
    cache = PARAMS / f"flow_feats_{series}.parquet"
    PARAMS.mkdir(exist_ok=True)
    f = pd.read_parquet(cache) if cache.exists() else None
    if f is None or f.index.max() < df.index.max() or len(f) < len(df) or not f.index.isin(df.index).all():
        f = build_feats(series, df, until=None if cutoff is None else cutoff.date())
        f.to_parquet(cache)
    df = pd.concat([df, f.loc[df.index]], axis=1)
    X = design(df)
    fit = df[df.rv_fut > 0]
    beta, *_ = np.linalg.lstsq(design(fit), np.log(fit.rv_fut), rcond=None)
    d = df.dropna(subset=["iv"])
    d = d[d.h.isin(H) & (d.iv > 0)]
    thr = float((d.iv / np.exp(design(d) @ beta)).quantile(pct))
    tag = "" if cutoff is None else "_until_" + cutoff.strftime("%Y%m%dT%H%M")
    name = f"flow_model_{series}{tag}.json"
    (PARAMS / name).write_text(json.dumps({
        "series": series, "fit_until": str(cutoff or df.close.max()), "n_markets": int(df.ticker.nunique()),
        "beta": [float(x) for x in beta], "ratio_threshold": thr, "ratio_pct": pct, "features": FEATURES}, indent=1))
    return name
