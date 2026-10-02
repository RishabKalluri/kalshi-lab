"""Screen 6 (H3): 8:30 ET is the US macro release time (jobless claims every Thursday; CPI, NFP, PPI, retail sales on
other days). Is the 8:30 window's vol step (vol +0.40 vs the month) underpriced like 9:30? Realized vol, iv gap and
underdog PnL (first checkpoint h 240-600, 10-45c) by weekday, both halves."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "strategies/us-hours-vol/research")
from iv_gap import load

for s in ["KXETH15M", "KXSOL15M", "KXBTC15M"]:
    d = load(s)
    x = d[(d.q == "08:30") & ~d.wkend].copy()
    x["dow"] = x.et.dt.day_name().str[:3]
    v = x[x.h == 840]
    v = v.assign(lv=np.log(v.rv_fut / v.S))
    allv = d[(d.h == 840) & ~d.wkend & (d.rv_fut > 0)]
    base = np.log(allv.rv_fut / allv.S).mean()
    b = x[np.minimum(x.mid, 1 - x.mid).between(0.10, 0.45) & x.next_ask.notna() & x.next_bid.notna() & x.h.between(240, 600)]
    pm = b.sort_values("h", ascending=False).groupby("ticker").first()
    g = x[x.iv.notna() & (x.iv > 0) & (x.rv_fut > 0) & x.h.between(240, 600)]
    print(f"== {s} 08:30 window by weekday")
    print(pd.DataFrame({"lvol_vs_weekday": v.groupby("dow").lv.mean() - base,
                        "iv_fut": g.groupby("dow").apply(lambda z: np.log(z.iv / z.rv_fut).median()),
                        "dogA": pm[pm.half == "A"].groupby("dow").dog.mean(), "dogB": pm[pm.half == "B"].groupby("dow").dog.mean(),
                        "n": pm.groupby("dow").size()}).round(2).to_string())
