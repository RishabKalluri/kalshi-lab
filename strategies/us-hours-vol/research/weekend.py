"""Screen 5 (H2): weekend vol is 0.6-0.9x weekday. Does the market price that? log(iv/rv_fut) and favourite /
underdog PnL at next fills by day type (weekday, Fri after 16:00 ET, Sat, Sun before 18:00 ET, Sun evening), both halves."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "strategies/us-hours-vol/research")
from iv_gap import load

for s in sys.argv[1:] or ["KXETH15M", "KXSOL15M", "KXBTC15M"]:
    d = load(s)
    dow, hr = d.et.dt.dayofweek, d.et.dt.hour
    d["dt"] = np.select([(dow == 4) & (hr >= 16), dow == 5, (dow == 6) & (hr < 18), dow == 6, (dow == 0) & (hr < 4)],
                        ["Fri>16", "Sat", "Sun<18", "Sun>18", "Mon<04"], "weekday")
    x = d[d.iv.notna() & (d.iv > 0) & (d.rv_fut > 0) & np.minimum(d.mid, 1 - d.mid).between(0.10, 0.45)
          & d.next_ask.notna() & d.next_bid.notna() & d.h.between(60, 600)].copy()
    x["g"] = np.log(x.iv / x.rv_fut)
    x["gt"] = np.log(x.iv / x.rv_15m)
    print(f"\n== {s}")
    print(x.groupby(["dt", "half"]).agg(iv_fut=("g", "median"), iv_trail=("gt", "median"), fav=("fav", "mean"),
                                         dog=("dog", "mean"), n=("g", "size")).unstack().round(2).to_string())
