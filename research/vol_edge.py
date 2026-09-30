"""Conditional edge: when implied vol is high relative to forecast (market too uncertain), favorites should
be underpriced; when low, underdogs. PnL per contract of buying the favorite (or underdog) at the
trade-implied ask, after fees, bucketed by iv / forecast. Train/test split by date."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
series = sys.argv[1] if len(sys.argv) > 1 else "KXBTC15M"
df = pd.read_parquet(Path(__file__).parent / "data" / f"{series}.parquet")
df["hour"] = df.close.dt.hour
split = df.close.quantile(0.5)

# Same HAR + hour-of-day forecast as vol_analysis.py, fit on train only.
tr = df[(df.close < split) & (df.rv_fut > 0.05)]
X = lambda d: np.column_stack([np.ones(len(d)), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
                               *[(d.hour == hh).astype(float) for hh in range(1, 24)], np.log(d.h)])
beta, *_ = np.linalg.lstsq(X(tr), np.log(tr.rv_fut), rcond=None)
df["rv_fc"] = np.exp(X(df) @ beta)
df = df.dropna(subset=["iv"])
df["ratio"] = df.iv / df.rv_fc
fee = lambda p: 0.07 * p * (1 - p)
fav_yes = df.mid > 0.5
df["fav_cost"] = np.where(fav_yes, df.ask, 1 - df.bid)
df["fav_win"] = np.where(fav_yes, df.y, 1 - df.y)
df["fav_pnl"] = df.fav_win - df.fav_cost - fee(df.fav_cost)
df["dog_cost"] = np.where(fav_yes, 1 - df.bid, df.ask)
df["dog_pnl"] = (1 - df.fav_win) - df.dog_cost - fee(df.dog_cost)
df["half"] = np.where(df.close < split, "train", "test")

qs = df[df.half == "train"].ratio.quantile([0, .2, .4, .6, .8, 1]).to_numpy().copy()
qs[0], qs[-1] = 0, np.inf
df["q"] = pd.cut(df.ratio, qs, labels=[f"Q{i+1}" for i in range(5)])
for hset in ([840, 720, 600, 480], [360, 300, 240], [180, 120, 90, 60]):
    d = df[df.h.isin(hset)]
    g = d.groupby(["q", "half"], observed=True).agg(n=("fav_pnl", "size"), ratio=("ratio", "median"),
                                                    fav=("fav_pnl", "mean"), dog=("dog_pnl", "mean"),
                                                    fav_price=("fav_cost", "mean")).unstack("half")
    print(f"\nh in {hset}: cents per contract after fees (favorite at ask | underdog at ask)")
    for q in g.index:
        r = g.loc[q]
        print(f"  {q} ratio~{r[('ratio','train')]:.2f}  train fav {r[('fav','train')]*100:+5.2f} dog {r[('dog','train')]*100:+5.2f}"
              f" (n={int(r[('n','train')])}, fav px {r[('fav_price','train')]:.2f})"
              f"  | test fav {r[('fav','test')]*100:+5.2f} dog {r[('dog','test')]*100:+5.2f} (n={int(r[('n','test')])})")
