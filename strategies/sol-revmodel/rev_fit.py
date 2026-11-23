"""Fit the open-reversal ridge model on data before a cutoff (the strategy's fit() hook).

Per window (one row per KXSOL15M market at h=840, the first-minute fill): features of the previous window's move
(z, late confirmation zl, Binance volume vs the 14-day same-slot median relv, clock) -> target = net PnL of fading the
move at the next real fill. Ridge, refit before each month on earlier windows only. Per-day minute spot means and slot
volumes are cached in params/daily/ so refits only read new days.
"""

import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PARAMS = Path(__file__).parent / "params"
BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
CACHE = Path(tempfile.gettempdir()) / "sol_revmodel_daily"   # outside params/: the lockbox sandbox must not leave subfolders there
FEATS = ["az", "az2", "lr", "azlr", "wk", "us", "al", "alaz", "alpos2"]


def design(t):
    return np.column_stack([t["az"], t["az"] ** 2, t["lr"], t["az"] * t["lr"], t["wk"], t["us"], t["al"],
                            t["al"] * t["az"], np.clip(t["al"], -4, 4) ** 2 * (t["al"] > 0)])


def features(z, zl, relv, close):
    """Dict of arrays/scalars used by design(): close is a tz-aware UTC timestamp (window close)."""
    al = np.sign(z) * zl
    c = pd.DatetimeIndex(close) if np.ndim(close) else pd.DatetimeIndex([close])
    return {"az": np.abs(z), "lr": np.log(relv), "wk": (c.dayofweek >= 5).astype(float),
            "us": ((c.hour >= 13) & (c.hour <= 21)).astype(float), "al": al}


def _day(series_dir, flow_dir, day):
    """(minute means 1440, slot volumes 96) for one UTC day, cached."""
    f = CACHE / f"{day}.npz"
    try:
        z = np.load(f)
        return z["m1"], z["v"]
    except Exception:
        pass
    from kalshi_lab.recorder.sink import EXT, read_lines
    m1 = np.full(1440, np.nan)
    p = series_dir / f"{day}{EXT}"
    if p.exists():
        t, px = [], []
        for line in read_lines(p):
            d = json.loads(line)
            t.append(d["t"] // 10**9)
            px.append(d["m"]["price"])
        t, px = np.array(t), np.array(px)
        base = int(pd.Timestamp(day, tz="UTC").timestamp())
        mi = (t - base) // 60
        ok = (mi >= 0) & (mi < 1440)
        s = np.bincount(mi[ok], weights=px[ok], minlength=1440)[:1440]
        n = np.bincount(mi[ok], minlength=1440)[:1440]
        m1 = np.where(n > 0, s / np.maximum(n, 1), np.nan)
    v = np.full(96, np.nan)
    q = flow_dir / f"{day}.parquet"
    if q.exists():
        x = pd.read_parquet(q, columns=["t", "buy", "sell"])
        base = int(pd.Timestamp(day, tz="UTC").timestamp())
        slot = (x.t.to_numpy() - base - 1) // 900
        ok = (slot >= 0) & (slot < 96)
        v = np.bincount(slot[ok], weights=(x.buy + x.sell).to_numpy()[ok], minlength=96)[:96]
    try:
        CACHE.mkdir(parents=True, exist_ok=True)
        os.chmod(CACHE, 0o777)
        tmp = f.with_name(f.name + f".{os.getpid()}.tmp.npz")
        np.savez(tmp, m1=m1, v=v)
        os.chmod(tmp, 0o666)
        os.replace(tmp, f)
    except OSError:
        pass
    return m1, v


def _dataset(series, cutoff):
    from kalshi_lab.validate import LOCKBOX_START
    full = cutoff > pd.Timestamp(LOCKBOX_START)
    path = ROOT / "research" / "data" / f"{series}{'_all' if full else ''}.parquet"
    target = cutoff if not full else cutoff
    if path.exists():
        df = pd.read_parquet(path)
        if df.close.max() >= min(target, pd.Timestamp(LOCKBOX_START)) - pd.Timedelta(days=2):
            return df
    subprocess.check_call([sys.executable, str(ROOT / "research" / "build_dataset.py"), series]
                          + (["--include-lockbox"] if full else []), cwd=ROOT)
    return pd.read_parquet(path)


def fit_model(series, until=None, alpha=30.0, thr=0.04):
    from kalshi_lab.data.flow import flow_sources
    from kalshi_lab.recorder.config import spot_map
    cutoff = pd.Timestamp(until, tz="UTC") if until else pd.Timestamp.now(tz="UTC")
    df = _dataset(series, cutoff)
    df = df[df.close < cutoff]
    spot = spot_map([series], backfill=True)[series][0]
    fdir = flow_sources(series)["binance"]
    from kalshi_lab.data.flow import FLOW
    fdir = FLOW / fdir
    days = pd.date_range(df.close.min().normalize() - pd.Timedelta(days=16), df.close.max().normalize(), freq="D")
    m1, vol = [], []
    for d in days:
        a, b = _day(BF / "spot" / spot, fdir, d.strftime("%Y-%m-%d"))
        m1.append(a)
        vol.append(b)
    idx1 = pd.date_range(days[0], periods=len(days) * 1440, freq="1min", tz="UTC")
    M1 = pd.Series(np.concatenate(m1), index=idx1)
    V = pd.Series(np.concatenate(vol), index=pd.date_range(days[0], periods=len(days) * 96, freq="15min", tz="UTC"))
    med = pd.concat([V.shift(96 * i) for i in range(1, 15)], axis=1).median(axis=1)
    relv = V / med
    o = df[df.h == 840].sort_values("close").copy()
    ok = (o.close - o.close.shift(1)).dt.total_seconds() == 900
    o["z"] = (np.log(o.K / o.K.shift(1)) / (o.rv_60m / o.S * np.sqrt(900))).where(ok)
    op = o.close - pd.Timedelta("15min")
    a1 = M1.reindex(op - pd.Timedelta("1min")).values
    a0 = M1.reindex(op - pd.Timedelta("6min")).values
    o["zl"] = (a1 - a0) / (o.rv_60m.values * np.sqrt(300))
    o["relv"] = relv.reindex(op - pd.Timedelta("15min")).values
    p = np.where(o.z > 0, 1 - o.next_bid, o.next_ask)
    y = np.where(o.z > 0, 1 - o.y, o.y)
    o["pnl"] = y - p - 0.07 * p * (1 - p)
    o = o.dropna(subset=["z", "zl", "relv", "pnl"])
    o = o[o.relv > 0]
    from sklearn.linear_model import Ridge
    ft = features(o.z.to_numpy(), o.zl.to_numpy(), o.relv.to_numpy(), o.close)
    X = design(ft)
    r = Ridge(alpha=alpha).fit(X, o.pnl.to_numpy())
    tag = "_until_" + cutoff.strftime("%Y%m%dT%H%M")
    name = f"rev_model_{series}{tag}.json"
    PARAMS.mkdir(exist_ok=True)
    (PARAMS / name).write_text(json.dumps({"series": series, "fit_until": str(cutoff), "n": int(len(o)),
                                           "coef": [float(c) for c in r.coef_], "intercept": float(r.intercept_),
                                           "alpha": alpha, "thr": thr, "mean_pnl": float(o.pnl.mean())}, indent=1))
    return name
