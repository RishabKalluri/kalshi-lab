"""Open-of-window screen on XRP/DOGE: is the early next-fill price off a driftless spot-vs-strike model?
Dev data only (dataset stops at lockbox). Halves A/B by date. Edge in cents per contract after fee."""
import sys
import numpy as np, pandas as pd
from scipy.stats import norm
fee = lambda p: 0.07*p*(1-p)
for s in ["KXXRP15M","KXDOGE15M"]:
    d = pd.read_parquet(f"research/data/{s}.parquet")
    print(s)
    for h in (840, 720, 600):
        x = d[d.h==h].dropna(subset=["next_ask","next_bid","rv_60m","D"]).copy()
        x["fair"] = norm.cdf(x.D/(x.rv_60m*np.sqrt(x.h-40)))
        mid = x.close.quantile(.5)
        print(f" h={h} n={len(x)} fills/market: ask {x.next_ask.notna().mean():.2f}")
        for nm, g in (("A", x[x.close<mid]), ("B", x[x.close>=mid])):
            out=[]
            for thr in (0.05, 0.10):
                buy = g.fair - g.next_ask > thr; sell = g.next_bid - g.fair > thr
                pnl = np.r_[(g.y-g.next_ask-fee(g.next_ask))[buy], (g.next_bid-g.y-fee(1-g.next_bid))[sell]]
                out.append(f"thr {thr}: {pnl.mean()*100 if len(pnl) else np.nan:+5.2f}c n={len(pnl)} se={pnl.std()/max(1,len(pnl))**.5*100:.1f}")
            # plain: buy cheap/ sell dear by price bucket
            print(f"   {nm}: " + " | ".join(out))
