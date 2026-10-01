"""Inside the settlement window: when spot has crossed the strike against the accumulated average, which wins?"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
series = sys.argv[1]
df = pd.read_parquet(Path(__file__).resolve().parents[3] / "research/data/settle-lockin" / f"{series}_lockin.parquet")
df = df[(df.close < "2026-08-20") & ((df.K / df.ev - 1).abs() < 0.05) & (df.h < 60)]
df["half"] = np.where(df.close < pd.Timestamp("2026-05-01", tz="UTC"), "A", "B")
df["month"] = df.close.dt.strftime("%m")
fee = lambda P: 0.07 * P * (1 - P)
sig = df.rv_60m * np.sqrt(60)
# projected settlement average assuming spot stays put: w*a_past + (1-w)*S
w = (60 - df.h) / 60
df["proj"] = w * df.a_past + (1 - w) * df.S
df["zp"] = (df.proj - df.K) / sig      # projected avg vs strike, in 1-min moves
df["zs"] = (df.S - df.K) / sig         # spot vs strike
cross = np.sign(df.zp) != np.sign(df.zs)
for name, g0 in [("cross (spot vs avg disagree)", df[cross]), ("all", df)]:
    print("==", name, len(g0))
    for hb, g1 in g0.groupby(pd.cut(g0.h, [0, 15, 30, 45, 59]), observed=True):
        # buy the side the projected average favours, at the next real fill
        yes = g1.zp > 0
        price = np.where(yes, g1.next_ask, 1 - g1.next_bid)
        win = np.where(yes, g1.y, 1 - g1.y)
        ok = ~np.isnan(price)
        pnl = (win - price - fee(price))[ok] * 100
        hal = g1.half.values[ok]
        s = " | ".join(f"{h}: {pnl[hal==h].mean():+.2f} n={np.sum(hal==h)}" for h in "AB")
        print(f"  h{hb}: projected-side win rate {win.mean():.3f}, avg price paid {np.nanmean(price):.3f}, pnl/ct {s}")
