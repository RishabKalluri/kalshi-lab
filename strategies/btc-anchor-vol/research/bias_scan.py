"""Structural biases at real next fills: YES-vs-NO preference, weekend/hour regimes. Dev data only."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]
fee = lambda P: 0.07 * P * (1 - P)
for series in ["KXETH15M", "KXSOL15M"]:
    d = pd.read_parquet(ROOT / "research/data" / f"{series}.parquet")
    d = d[(d.close < "2026-08-20") & (d.close >= "2026-01-15")].copy()
    d["half"] = np.where(d.close < pd.Timestamp("2026-05-01", tz="UTC"), "A", "B")
    d["yes_pnl"] = (d.y - d.next_ask - fee(d.next_ask)) * 100
    d["no_pnl"] = ((1 - d.y) - (1 - d.next_bid) - fee(d.next_bid)) * 100
    d["wkend"] = d.close.dt.dayofweek >= 5
    d["hb"] = pd.cut(d.close.dt.hour, [-1, 7, 12, 16, 20, 23], labels=["00-07", "08-12", "13-16", "17-20", "21-23"])
    d["pb"] = pd.cut(d.mid, [0, 0.1, 0.3, 0.5, 0.7, 0.9, 1])
    print(f"===== {series}")
    print("YES vs NO by price bucket and half (c/ct)")
    print(d.pivot_table(index="pb", columns="half", values=["yes_pnl", "no_pnl"], aggfunc="mean", observed=True).round(2).to_string())
    print("weekend / hour (YES+NO averaged = cost of trading)")
    d["any"] = d[["yes_pnl", "no_pnl"]].mean(axis=1)
    print(d.pivot_table(index=["wkend", "hb"], columns="half", values=["yes_pnl", "no_pnl"], aggfunc="mean", observed=True).round(2).to_string())
    # the 15-min return sign: does 'up' (YES) win more than the market thinks by month?
    d["month"] = d.close.dt.strftime("%m")
    print("YES pnl by month:", d.groupby("month").yes_pnl.mean().round(2).to_dict())
    print("NO pnl by month:", d.groupby("month").no_pnl.mean().round(2).to_dict())
