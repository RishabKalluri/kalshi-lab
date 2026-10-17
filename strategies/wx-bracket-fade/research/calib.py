import pandas as pd, numpy as np
df = pd.read_parquet("strategies/wx-bracket-fade/research/snaps.parquet")
df["y"] = (df.result == "yes").astype(float)
fee = lambda p: 0.07 * p * (1 - p)
rows = []
for side in ("yes", "no"):
    d = df.copy()
    if side == "yes":
        d = d[d.ask.notna() & (d.ask_age < 120)]; p = d.ask; d["pnl"] = d.y - p - fee(p)
    else:
        d = d[d.bid.notna() & (d.bid_age < 120)]; p = 1 - d.bid; d["pnl"] = (1 - d.y) - p - fee(p)
    d["pc"] = p
    d["bucket"] = pd.cut(p, [0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1])
    print(side)
    print(d.groupby("bucket", observed=True).pnl.agg(["mean", "count"]).round(4).T.to_string())
    print(d.groupby("h").pnl.agg(["mean", "count"]).round(4).T.to_string())
