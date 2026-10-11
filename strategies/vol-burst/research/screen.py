"""Screen: side PnL at the next real taker fill after fee, by vol-burst / iv features. Development data only."""
import sys, numpy as np, pandas as pd
pd.set_option("display.width", 200)

def fee(p): return np.ceil(7 * p * (1 - p)) / 100  # 1-contract taker fee, $

def load(series):
    d = pd.read_parquet(f"research/data/{series}.parquet")
    d = d[d.close < "2026-08-20"].copy()
    d["half"] = np.where(d.close < "2026-05-01", "A", "B")
    # underdog side
    dog_yes = d.mid < 0.5
    px = np.where(dog_yes, d.next_ask, 1 - d.next_bid)
    win = np.where(dog_yes, d.y == 1, d.y == 0)
    d["dog_px"] = px
    d["dog_pnl"] = (win - px - fee(px)) * 100
    fpx = np.where(~dog_yes, d.next_ask, 1 - d.next_bid)
    d["fav_px"] = fpx
    d["fav_pnl"] = ((~win) - fpx - fee(fpx)) * 100
    d["burst"] = d.rv_5m / d.rv_60m
    d["burst15"] = d.rv_5m / d.rv_15m
    d["iv5"] = d.iv / d.rv_5m
    return d

for series in sys.argv[1:] or ["KXETH15M", "KXSOL15M"]:
    d = load(series)
    for side in ["dog", "fav"]:
        lo, hi = (0.10, 0.45) if side == "dog" else (0.55, 0.90)
        s = d[(d[f"{side}_px"] >= lo) & (d[f"{side}_px"] <= hi) & d.h.between(120, 720)].dropna(subset=[f"{side}_pnl"])
        for feat in ["burst", "burst15", "iv5"]:
            s2 = s.dropna(subset=[feat]).copy()
            s2["q"] = pd.qcut(s2[feat], 10, labels=False, duplicates="drop")
            t = s2.groupby(["q", "half"])[f"{side}_pnl"].agg(["mean", "count"]).unstack()
            t["edge"] = s2.groupby("q")[feat].median()
            print(f"\n{series} {side} by {feat} decile (c/ct after fee, next fill, h 120-720)\n", t.round(2).to_string())
