"""Calibration of early fills by price bucket (taker buy at next_ask, taker sell at next_bid), halves A/B."""
import numpy as np, pandas as pd
fee = lambda p: 0.07*p*(1-p)
bins=[0,.2,.35,.45,.55,.65,.8,1]
for s in ["KXXRP15M","KXDOGE15M"]:
    d = pd.read_parquet(f"research/data/{s}.parquet"); d=d[d.h.isin((840,720))].dropna(subset=["next_ask","next_bid"])
    med=d.close.quantile(.5); print(s)
    for h in (840,720):
      x=d[d.h==h]
      for side in ("buy","sell"):
        row=[]
        for nm,g in (("A",x[x.close<med]),("B",x[x.close>=med])):
            p = g.next_ask if side=="buy" else g.next_bid
            pnl = (g.y-p-fee(p)) if side=="buy" else (p-g.y-fee(1-p))
            b=pd.cut(p,bins)
            r=pnl.groupby(b,observed=True).agg(["mean","count"])
            row.append(" ".join(f"{m*100:+.1f}({n})" for m,n in zip(r["mean"],r["count"])))
        print(f" h{h} {side}: A {row[0]}\n         B {row[1]}")
