"""Late favourite-longshot screen: buy the favourite at a fixed checkpoint near close, at the next real fill."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
series = sys.argv[1]
df = pd.read_parquet(Path(__file__).resolve().parents[3] / "research/data/settle-lockin" / f"{series}_lockin.parquet")
df = df[(df.close < "2026-08-20") & ((df.K / df.ev - 1).abs() < 0.05)]
df["month"] = df.close.dt.strftime("%m")
fee = lambda P: 0.07 * P * (1 - P)
lm = (df.last_buy + df.last_sell) / 2
df["fav_yes"] = lm > 0.5
df["price"] = np.where(df.fav_yes, df.next_ask, 1 - df.next_bid)
df["win"] = np.where(df.fav_yes, df.y, 1 - df.y)
df["pnl"] = (df.win - df.price - fee(df.price)) * 100
d = df.dropna(subset=["price"])
pb = pd.cut(d.price, [0.5, 0.7, 0.8, 0.85, 0.9, 0.93, 0.96, 0.99])
print("pnl c/ct by horizon x favourite price (n)")
print(d.pivot_table(index="h", columns=pb, values="pnl", aggfunc="mean", observed=True).round(2).to_string())
print(d.pivot_table(index="h", columns=pb, values="pnl", aggfunc="count", observed=True).to_string())
sel = d[(d.price >= 0.80) & (d.price <= 0.97)]
print("\nprice .80-.97, by horizon x month")
print(sel.pivot_table(index="h", columns="month", values="pnl", aggfunc="mean").round(2).to_string())
for hs in [(15, 45), (60, 120), (150, 300)]:
    g = sel[sel.h.between(*hs)]
    g1 = g.groupby("ticker").pnl.mean()  # cluster by market
    print(f"h {hs}: mean {g.pnl.mean():+.2f}, markets {len(g1)}, t(clustered) {g1.mean() / g1.std() * np.sqrt(len(g1)):+.2f}")
