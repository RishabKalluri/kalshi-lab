"""H5 screen: does the 08:00 UTC Deribit expiry shape ETH vol, and does Kalshi price it? Dev data only.

    uv run python strategies/eth-midrev/research/expiry_0800.py [SERIES]

1. Window realized vol (rv_fut at h=840, log, minus the month's weekday mean) by UTC window start 06:30-09:30, split
   EST (before Mar 8 / after Nov 1) vs EDT, and Friday vs Mon-Thu.
2. By UTC slot (weekdays, Fri vs Mon-Thu): median log(iv/rv_fut), underdog / favourite PnL at next real fill after fee,
   halves A (< May) / B.
"""
import sys
import numpy as np
import pandas as pd
sys.path.insert(0, "strategies/us-hours-vol/research")
from iv_gap import load  # noqa: E402

s = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
d = load(s)
d["utc"] = d.start.dt.strftime("%H:%M")
d["dow"] = d.start.dt.dayofweek
d["fri"] = np.where(d.dow == 4, "Fri", np.where(d.dow < 4, "Mon-Thu", "wkend"))
d["dst"] = np.where(d.et.dt.strftime("%z") == "-0400", "EDT", "EST")
d["mon"] = d.start.dt.strftime("%Y-%m")
w = d[(d.h == 840) & (d.rv_fut > 0) & (d.dow < 5)].copy()
w["lv"] = np.log(w.rv_fut)
w["lv"] -= w.groupby("mon").lv.transform("mean")
slots = [f"{h:02d}:{m:02d}" for h in range(6, 10) for m in (0, 15, 30, 45)]
print(f"== {s} 1. log window vol vs month weekday mean, by UTC start")
g = w[w.utc.isin(slots)].groupby(["utc", "fri", "dst"]).lv.mean().unstack(["fri", "dst"])
print(g.round(2).to_string())
x = d[(d.dow < 5) & d.utc.isin(slots) & d.iv.notna() & (d.iv > 0) & (d.rv_fut > 0) & d.mid.between(0.1, 0.9)].copy()
x["g"] = np.log(x.iv / x.rv_fut)
print(f"\n== 2. log(iv/rv_fut) and PnL (c) by UTC slot, all h; overall weekday g median "
      f"{np.log(d[(d.dow < 5) & (d.iv > 0) & (d.rv_fut > 0) & d.mid.between(0.1, 0.9)].eval('iv/rv_fut')).median():.2f}")
for fri in ("Fri", "Mon-Thu"):
    y = x[x.fri == fri]
    gg = y.groupby("utc").apply(lambda v: pd.Series(dict(
        g=v.g.median(), dogA=v[v.half == "A"].dog.mean(), dogB=v[v.half == "B"].dog.mean(),
        favA=v[v.half == "A"].fav.mean(), favB=v[v.half == "B"].fav.mean(), mk=v.ticker.nunique())), include_groups=False)
    print(f"-- {fri}")
    print(gg.round(2).to_string())
