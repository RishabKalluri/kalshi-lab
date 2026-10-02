"""Screen 7 (H4): the mirror of the 9:30 bell. After the 16:00 ET US close vol steps down (16:15-16:45 slots
-0.06..-0.18 vs +0.09 at 16:00); if the market carries session vol into the evening, iv is too high and the
favourite (55-90c) is cheap. First checkpoint h 240-600 per market, next real fill, fee, both halves; slots 16:00-17:00."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "strategies/us-hours-vol/research")
from iv_gap import load
from open_dog import HOL

for s in ["KXETH15M", "KXSOL15M", "KXBTC15M"]:
    d = load(s)
    d["hol"] = d.et.dt.strftime("%Y-%m-%d").isin(HOL)
    b = d[~d.wkend & ~d.hol & np.minimum(d.mid, 1 - d.mid).between(0.10, 0.45) & d.next_ask.notna() & d.next_bid.notna()
          & d.h.between(240, 600)]
    out = {}
    for slot in ["15:45", "16:00", "16:15", "16:30", "16:45", "17:00"]:
        pm = b[b.q == slot].sort_values("h", ascending=False).groupby("ticker").first()
        out[slot] = {"favA": pm[pm.half == "A"].fav.mean(), "favB": pm[pm.half == "B"].fav.mean(),
                     "se": pm.fav.std() / np.sqrt(len(pm)), "n": len(pm)}
    pm = b.sort_values("h", ascending=False).groupby("ticker").first()
    out["ALL"] = {"favA": pm[pm.half == "A"].fav.mean(), "favB": pm[pm.half == "B"].fav.mean(), "se": np.nan, "n": len(pm)}
    print(f"== {s}\n" + pd.DataFrame(out).T.round(2).to_string())
