"""Fit gbm-edge's two edge regressors on data before a cutoff (the strategy's fit() hook).

For every (market, checkpoint h) row of research/data/<SERIES>.parquet: edge of buying YES at the trade-implied ask
(y - ask - fee) and of buying NO at the trade-implied bid (bid - y - fee), regressed on spot-distance features:
z5 = D/(rv_5m sqrt h), z = D/(rv_60m sqrt h), mid, h. Pooled over the given series. Saved as a pickle in params/.
"""
import pickle
import subprocess
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PARAMS = Path(__file__).parent / "params"
H = [600, 480, 360, 300, 240, 180, 120, 90, 60]
FEATURES = ["z5", "z", "mid", "h"]


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


def fee(p):
    return 0.07 * p * (1 - p)


def features(D, rv5, rv60, mid, h):
    return np.column_stack([D / (rv5 * np.sqrt(h) + 1e-12), D / (rv60 * np.sqrt(h) + 1e-12), mid, h])


def fit_model(series: list[str], until=None) -> str:
    from sklearn.ensemble import HistGradientBoostingRegressor
    cutoff = pd.Timestamp(until, tz="UTC") if until else None
    frames = [_dataset(s, cutoff or pd.Timestamp.now(tz="UTC")) for s in series]
    d = pd.concat(frames)
    if cutoff is not None:
        d = d[d.close < cutoff]
    d = d[d.h.isin(H)].dropna(subset=["ask", "bid", "rv_5m", "rv_60m", "D"])
    d = d[(d.rv_5m > 0) & (d.rv_60m > 0)]
    X = features(d.D.values, d.rv_5m.values, d.rv_60m.values, d.mid.values, d.h.values)
    ey = (d.y - d.ask - fee(d.ask)).values
    en = (d.bid - d.y - fee(1 - d.bid)).values
    mk = lambda: HistGradientBoostingRegressor(max_depth=3, max_iter=150, learning_rate=0.05, min_samples_leaf=400,
                                               l2_regularization=5.0, random_state=0)
    my, mn = mk().fit(X, ey), mk().fit(X, en)
    tag = "all" if cutoff is None else cutoff.strftime("%Y%m%dT%H%M")
    PARAMS.mkdir(exist_ok=True)
    name = f"gbm_{'_'.join(s[2:5] for s in series)}_until_{tag}.pkl"
    with open(PARAMS / name, "wb") as f:
        pickle.dump({"yes": my, "no": mn, "n_markets": int(d.ticker.nunique()), "fit_until": str(cutoff)}, f)
    return name
