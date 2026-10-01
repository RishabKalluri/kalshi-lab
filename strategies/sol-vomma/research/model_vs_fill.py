"""Screen: vol-mixture ("vomma") fair value vs KXSOL15M real next fills. Development data only.

uv run python strategies/sol-vomma/research/screen.py
"""
import sys

import numpy as np
import pandas as pd
from scipy.stats import norm

LOCK = pd.Timestamp("2026-08-20", tz="UTC")
SPLIT = pd.Timestamp("2026-05-01", tz="UTC")
H = [360, 300, 240, 180, 120, 90, 60]

df = pd.read_parquet("research/data/KXSOL15M.parquet")
df = df[df.close < LOCK]
df = df.dropna(subset=["rv_5m", "rv_15m", "rv_60m", "rv_4h", "rv_fut", "D"])
df = df[(df.rv_5m > 0) & (df.rv_15m > 0) & (df.rv_60m > 0) & (df.rv_4h > 0) & (df.rv_fut > 0)].copy()
df["hour"] = df.close.dt.hour
# vol-of-vol state: how different is the last 5m from the last hour (log ratio), absolute
df["vov"] = np.abs(np.log(df.rv_5m / df.rv_60m))


def X(d):
    return np.column_stack([np.ones(len(d)), np.log(d.rv_5m), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
                            *[(d.hour == hh).astype(float) for hh in range(1, 24)], np.log(d.h)])


tr, te = df[df.close < SPLIT], df[df.close >= SPLIT]
beta, *_ = np.linalg.lstsq(X(tr), np.log(tr.rv_fut), rcond=None)
res_tr = np.log(tr.rv_fut) - X(tr) @ beta
# residual dispersion model: |res| ~ a + b*log h + c*vov  (vol-of-vol forecast)
Z = lambda d: np.column_stack([np.ones(len(d)), np.log(d.h), d.vov, np.log(d.rv_5m / d.rv_4h)])
g, *_ = np.linalg.lstsq(Z(tr), np.abs(res_tr), rcond=None)
std_res = res_tr / (Z(tr) @ g)
qs = np.quantile(std_res, (np.arange(50) + 0.5) / 50)  # empirical standardized residual distribution
print("resid sd", res_tr.std(), "by h", tr.assign(r=res_tr).groupby("h").r.std().round(3).to_dict())
print("disp model", np.round(g, 3))

for name, d in [("train", tr), ("test", te)]:
    d = d.copy()
    mu = X(d) @ beta
    s = Z(d) @ g
    tp = np.sqrt(np.maximum(d.h - 40, 5))
    d["p_point"] = norm.cdf(d.D / (np.exp(mu) * tp))
    sig = np.exp(np.asarray(mu)[:, None] + np.asarray(s)[:, None] * qs[None, :])
    d["p_mix"] = norm.cdf(d.D.values[:, None] / (sig * tp.values[:, None])).mean(1)
    # constant-dispersion mixture (no vov state)
    sig0 = np.exp(np.asarray(mu)[:, None] + res_tr.std() * norm.ppf((np.arange(50) + 0.5) / 50)[None, :])
    d["p_mix0"] = norm.cdf(d.D.values[:, None] / (sig0 * tp.values[:, None])).mean(1)
    d["p_oracle"] = norm.cdf(d.D / (d.rv_fut * tp))
    dd = d[d.h.isin(H) & d.next_ask.notna() & d.next_bid.notna()]
    eps = 1e-4
    ll = lambda p, y: -np.mean(y * np.log(np.clip(p, eps, 1 - eps)) + (1 - y) * np.log(np.clip(1 - p, eps, 1 - eps)))
    nm = (dd.next_ask + dd.next_bid) / 2
    print(f"\n== {name}: n={len(dd)} (rows with both next fills at checkpoints)")
    for k, p in [("next-fill mid", nm), ("mid", dd.mid), ("point", dd.p_point), ("mix0", dd.p_mix0),
                 ("mix", dd.p_mix), ("oracle rv_fut", dd.p_oracle)]:
        print(f"  logloss {k:14s} {ll(p, dd.y):.4f}")
    # trading at real next fills
    a = d[d.h.isin(H)]
    for k in ["p_point", "p_mix0", "p_mix"]:
        out = []
        for m in [0.0, 0.02, 0.04, 0.06]:
            fee_a = 0.07 * a.next_ask * (1 - a.next_ask)
            fee_b = 0.07 * a.next_bid * (1 - a.next_bid)
            buy = a.next_ask.notna() & (a[k] - a.next_ask - fee_a > m)
            sell = a.next_bid.notna() & (a.next_bid - a[k] - fee_b > m)
            pnl = np.concatenate([(a.y - a.next_ask - fee_a)[buy], (a.next_bid - a.y - fee_b)[sell]])
            if len(pnl) > 30:
                out.append(f"m={m:.2f}: n={len(pnl)} {100 * pnl.mean():+.2f}c ±{196 * pnl.std() / np.sqrt(len(pnl)):.2f}")
        print(f"  {k}: " + " | ".join(out))
    # where is the market wrong: bucket by z
    a = a[a.next_ask.notna()].copy()
    a["z"] = a.D / (np.exp(X(a) @ beta) * np.sqrt(np.maximum(a.h - 40, 5)))
    a["fav"] = np.where(a.z > 0, a.y, 1 - a.y)
    a["favpx"] = np.where(a.z > 0, a.next_ask, 1 - a.next_bid)
    a["zb"] = pd.cut(a.z.abs(), [0, 0.3, 0.6, 1.0, 1.41, 2.0, 3.0, 9])
    print(a.groupby("zb", observed=True).agg(n=("fav", "size"), win=("fav", "mean"), px=("favpx", "mean"),
                                             mix=("p_mix", lambda s: np.nan)).drop(columns="mix").round(3))
