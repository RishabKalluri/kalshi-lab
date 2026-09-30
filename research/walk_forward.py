"""Walk-forward test of the vol-favorite signal: for each month, fit the vol forecast and the entry
threshold on ALL EARLIER months only, then trade that month (next-trade fills, after fees).

    uv run python research/walk_forward.py KXETH15M [--min-train-months 2] [--pct 0.8]
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

ap = argparse.ArgumentParser()
ap.add_argument("series")
ap.add_argument("--min-train-months", type=int, default=2)
ap.add_argument("--pct", type=float, default=0.8)
a = ap.parse_args()
df = pd.read_parquet(Path(__file__).parent / "data" / f"{a.series}.parquet")
df["hour"] = df.close.dt.hour
df["month"] = df.close.dt.strftime("%Y-%m")
fee = lambda p: 0.07 * p * (1 - p)
H = [360, 300, 240, 180, 120, 90, 60]
X = lambda d: np.column_stack([np.ones(len(d)), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
                               *[(d.hour == hh).astype(float) for hh in range(1, 24)], np.log(d.h)])
df = df.dropna(subset=["rv_15m", "rv_60m", "rv_4h"])
df = df[(df.rv_15m > 0) & (df.rv_60m > 0) & (df.rv_4h > 0)]
months = sorted(df.month.unique())
rng = np.random.default_rng(0)


def ci(t):
    per = t.groupby("ticker").pnl.agg(["sum", "size"])
    if len(per) < 5:
        return (np.nan, np.nan)
    idx = rng.integers(0, len(per), size=(2000, len(per)))
    s, c = per["sum"].to_numpy()[idx].sum(1), per["size"].to_numpy()[idx].sum(1)
    return tuple(np.percentile(100 * s / c, [2.5, 97.5]))


rows, trades = [], []
for i, m in enumerate(months):
    if i < a.min_train_months:
        continue
    tr = df[df.month < m]
    te = df[df.month == m].copy()
    fit = tr[tr.rv_fut > 0.05]
    beta, *_ = np.linalg.lstsq(X(fit), np.log(fit.rv_fut), rcond=None)
    trh = tr.dropna(subset=["iv"])
    trh = trh[trh.h.isin(H)]
    thr = float((trh.iv / np.exp(X(trh) @ beta)).quantile(a.pct))
    te = te.dropna(subset=["iv"])
    te = te[te.h.isin(H)]
    te["ratio"] = te.iv / np.exp(X(te) @ beta)
    sig = te[te.ratio > thr].copy()
    fav_yes = sig.mid > 0.5
    sig["fill"] = np.where(fav_yes, sig.next_ask, 1 - sig.next_bid)
    sig = sig.dropna(subset=["fill"])
    sig["win"] = np.where(sig.mid > 0.5, sig.y, 1 - sig.y)
    sig["pnl"] = sig.win - sig.fill - fee(sig.fill)
    lo, hi = ci(sig)
    daily = sig.groupby(sig.close.dt.date).pnl.sum()
    rows.append(dict(month=m, train_months=i, threshold=round(thr, 3), signals=len(sig), markets=sig.ticker.nunique(),
                     c_per_contract=round(100 * sig.pnl.mean(), 2) if len(sig) else np.nan,
                     ci_lo=round(lo, 2), ci_hi=round(hi, 2), days_pos=f"{(daily > 0).sum()}/{len(daily)}",
                     avg_fav_price=round(sig.fill.mean(), 3) if len(sig) else np.nan))
    trades.append(sig[["ticker", "close", "h", "fill", "win", "pnl"]].assign(month=m))

res = pd.DataFrame(rows)
allt = pd.concat(trades)
lo, hi = ci(allt)
daily = allt.groupby(allt.close.dt.date).pnl.sum()
print(f"{a.series}: walk-forward, threshold = {a.pct:.0%} quantile of the ratio on all earlier months, next-trade fills after fees\n")
print(res.to_string(index=False))
print(f"\nPOOLED out-of-sample: {100 * allt.pnl.mean():+.2f}c/contract over {len(allt):,} signals / "
      f"{allt.ticker.nunique():,} markets, 95% CI [{lo:+.2f}, {hi:+.2f}], "
      f"months positive {(res.c_per_contract > 0).sum()}/{len(res)}, days positive {(daily > 0).sum()}/{len(daily)}")
out = Path(__file__).parent / "data" / f"walk_forward_{a.series}.csv"
res.to_csv(out, index=False)
