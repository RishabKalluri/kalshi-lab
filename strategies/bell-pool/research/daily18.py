"""Screen: daily CME reopen 18:00 ET Mon-Thu (and Fri 18:00 placebo: CME closed) -> underdog PnL, halves."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "strategies/bell-vol/research")
from opens import load
for s in ["KXETH15M", "KXBTC15M", "KXSOL15M"]:
    d = load(s); loc = d.start.dt.tz_convert("America/New_York")
    d["q"] = loc.dt.strftime("%H:%M"); d["dow"] = loc.dt.dayofweek
    d["dmid"] = np.minimum(d.mid, 1 - d.mid)
    b = d[d.dmid.between(0.10, 0.45) & d.next_ask.notna() & d.next_bid.notna() & d.h.between(240, 600)]
    for name, sel in [("Mon-Thu 18:00", b.dow.isin([0,1,2,3])), ("Fri 18:00", b.dow == 4), ("Mon-Thu 17:45", None), ("Mon-Thu 18:15", None)]:
        if sel is None:
            q = name.split()[1]; x = b[(b.q == q) & b.dow.isin([0,1,2,3])]
        else: x = b[sel & (b.q == "18:00")]
        pm = x.sort_values("h", ascending=False).groupby("ticker").first()
        a, bb = pm[pm.half == "A"].dog, pm[pm.half == "B"].dog
        print(s, f"{name:14s} n={len(pm):3d} mean {pm.dog.mean():+5.1f} se {pm.dog.std()/max(1,len(pm))**.5:4.1f}  A {a.mean():+5.1f}({len(a)}) B {bb.mean():+5.1f}({len(bb)})")
