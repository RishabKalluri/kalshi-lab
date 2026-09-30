"""Robustness for 'buy the favorite when implied vol is high vs forecast'.

Forecast (HAR + hour of day) and the ratio threshold are fit on the first half of dates only.
Fills at the next same-side taker trade within 10s (not the last print). CI: bootstrap by market.

    uv run python research/vol_favorite_robust.py KXETH15M
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
df = pd.read_parquet(Path(__file__).parent / "data" / f"{series}.parquet")
df["hour"] = df.close.dt.hour
split = df.close.quantile(0.5)
tr = df[(df.close < split) & (df.rv_fut > 0.05)]
X = lambda d: np.column_stack([np.ones(len(d)), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
                               *[(d.hour == hh).astype(float) for hh in range(1, 24)], np.log(d.h)])
beta, *_ = np.linalg.lstsq(X(tr), np.log(tr.rv_fut), rcond=None)
df["rv_fc"] = np.exp(X(df) @ beta)
df = df.dropna(subset=["iv"])
df = df[df.h.isin([360, 300, 240, 180, 120, 90, 60])]
df["ratio"] = df.iv / df.rv_fc
fee = lambda p: 0.07 * p * (1 - p)
fav_yes = df.mid > 0.5
df["fill"] = np.where(fav_yes, df.next_ask, 1 - df.next_bid)          # realistic cost of the favorite
df["stale"] = np.where(fav_yes, df.ask, 1 - df.bid)
df["win"] = np.where(fav_yes, df.y, 1 - df.y)
df["pnl_next"] = df.win - df.fill - fee(df.fill)
df["pnl_stale"] = df.win - df.stale - fee(df.stale)
df["half"] = np.where(df.close < split, "train", "test")
cuts = df[df.half == "train"].ratio.quantile([0.6, 0.8]).to_numpy()
print(f"{series}: ratio thresholds from train: 60th pct {cuts[0]:.2f}, 80th pct {cuts[1]:.2f}\n")


def boot(d, col, n=3000):
    per = d.groupby("ticker")[col].agg(["sum", "size"])
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(per), size=(n, len(per)))
    s, c = per["sum"].to_numpy()[idx].sum(1), per["size"].to_numpy()[idx].sum(1)
    return np.percentile(s / c, [2.5, 97.5])


for name, lo in (("ratio > 60th pct (Q4+Q5)", cuts[0]), ("ratio > 80th pct (Q5)", cuts[1])):
    print(name)
    for half in ("train", "test"):
        d = df[(df.half == half) & (df.ratio > lo)].dropna(subset=["fill"])
        a, b = boot(d, "pnl_next")
        per_day = d.groupby(d.close.dt.date).pnl_next.sum()
        print(f"  {half:>5}: next-trade fill {d.pnl_next.mean()*100:+5.2f}c  (stale {d.pnl_stale.mean()*100:+5.2f}c)  "
              f"n={len(d)} markets={d.ticker.nunique()}  95% CI [{a*100:+.2f}, {b*100:+.2f}]  days+ {(per_day>0).sum()}/{len(per_day)}")
    d = df[df.ratio > lo].dropna(subset=["fill"])
    print("  by horizon (both halves):", d.groupby("h").pnl_next.agg(lambda x: f"{x.mean()*100:+.1f}c/{len(x)}").to_dict())
    print("  by fav price:", d.groupby(pd.cut(d.fill, [0.5, 0.7, 0.8, 0.9, 0.95, 1.0]), observed=True)
          .pnl_next.agg(lambda x: f"{x.mean()*100:+.1f}c/{len(x)}").to_dict())
    print()
