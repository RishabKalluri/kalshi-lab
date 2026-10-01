"""Market-relative vomma: take the market's own price as the point-vol price, apply the vol-uncertainty
(mixture) correction with our vol-of-vol forecast, and check against real next fills. Development data only.

uv run python strategies/sol-vomma/research/market_vomma.py
"""
import numpy as np
import pandas as pd
from scipy.stats import norm

LOCK = pd.Timestamp("2026-08-20", tz="UTC")
SPLIT = pd.Timestamp("2026-05-01", tz="UTC")
H = [360, 300, 240, 180, 120, 90, 60]
EPS = norm.ppf((np.arange(40) + 0.5) / 40)

df = pd.read_parquet("research/data/KXSOL15M.parquet")
df = df[(df.close < LOCK) & df.h.isin(H)]
df = df.dropna(subset=["rv_5m", "rv_15m", "rv_60m", "rv_4h", "rv_fut", "mid"])
df = df[(df.rv_5m > 0) & (df.rv_15m > 0) & (df.rv_60m > 0) & (df.rv_4h > 0) & (df.rv_fut > 0)].copy()
df = df[(df.mid > 0.02) & (df.mid < 0.98)]
df["hour"] = df.close.dt.hour
df["vov"] = np.abs(np.log(df.rv_5m / df.rv_60m))
X = lambda d: np.column_stack([np.ones(len(d)), np.log(d.rv_5m), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
                               *[(d.hour == hh).astype(float) for hh in range(1, 24)], np.log(d.h)])
Z = lambda d: np.column_stack([np.ones(len(d)), np.log(d.h), d.vov, np.log(d.rv_5m / d.rv_4h)])
tr = df[df.close < SPLIT]
beta, *_ = np.linalg.lstsq(X(tr), np.log(tr.rv_fut), rcond=None)
res = np.log(tr.rv_fut) - X(tr) @ beta
g, *_ = np.linalg.lstsq(Z(tr), np.abs(res), rcond=None)
df["s"] = np.clip(Z(df) @ g, 0.05, 1.0) * np.sqrt(np.pi / 2)  # E|N(0,s)| = s*sqrt(2/pi)
zm = norm.ppf(df.mid.values)
df["zm"] = zm
df["p_adj"] = norm.cdf(zm[:, None] * np.exp(-df.s.values[:, None] * EPS[None, :])).mean(1)
df["corr"] = df.p_adj - df.mid
df["vomma"] = norm.pdf(zm) * zm * (2 - zm ** 2)  # in z-units
# the favourite's view
fav = df.mid > 0.5
df["fwin"] = np.where(fav, df.y, 1 - df.y)
df["fpx"] = np.where(fav, df.next_ask, 1 - df.next_bid)
df["fcorr"] = np.where(fav, df["corr"], -df["corr"])
df["fee"] = 0.07 * df.fpx * (1 - df.fpx)
df["fpnl"] = df.fwin - df.fpx - df.fee
df["half"] = np.where(df.close < SPLIT, "Jan-Apr", "May-Aug")
d = df.dropna(subset=["fpx"])
d["zb"] = pd.cut(d.zm.abs(), [0, 0.4, 0.8, 1.2, 1.41, 1.8, 2.4, 9])
d["sb"] = d.groupby("half").s.transform(lambda x: pd.qcut(x, 3, labels=["lo", "mid", "hi"]))
pd.set_option("display.width", 200)
print("buy-the-favourite PnL (c/contract, after fee) by |z_market| and vol-of-vol tercile")
t = d.groupby(["half", "zb", "sb"], observed=True).agg(n=("fpnl", "size"), pnl=("fpnl", "mean"),
                                                         corr=("fcorr", "mean")).reset_index()
t["pnl"] *= 100
t["corr"] *= 100
print(t.pivot_table(index="zb", columns=["half", "sb"], values="pnl", observed=True).round(2))
print(t.pivot_table(index="zb", columns=["half", "sb"], values="corr", observed=True).round(2))
print(t.pivot_table(index="zb", columns=["half", "sb"], values="n", observed=True))

# trade the correction: buy favourite if fcorr > fee + m, buy underdog if -fcorr > fee + m (underdog at its fill)
d["upx"] = np.where(d.mid > 0.5, 1 - d.next_bid, d.next_ask)
d["upnl"] = (1 - d.fwin) - d.upx - 0.07 * d.upx * (1 - d.upx)
for half, x in d.groupby("half"):
    for m in [0.0, 0.005, 0.01, 0.02]:
        b = x[x.fcorr > m]
        u = x[(-x.fcorr > m) & x.upx.notna()]
        print(half, f"m={m}: fav n={len(b)} {100*b.fpnl.mean():+.2f}c  | dog n={len(u)} {100*u.upnl.mean():+.2f}c")
