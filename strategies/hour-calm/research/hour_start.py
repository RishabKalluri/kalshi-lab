"""H2 screen: is the window that starts on the hour (:00) more volatile than the market expects?
By minute of the window start (:00/:15/:30/:45): vol vs month mean (h=840), median log(iv/rv_fut) by horizon band,
underdog / favourite PnL at next real fill after fee, halves A/B; per coin. Excludes the 9:30 ET window
(us-hours-vol's bell) and NY 10:00 (its neighbour) to keep the effect separate. Development data only."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "strategies/hour-calm/research")
from opens import load


def main(series):
    for s in series:
        d = load(s)
        et = d.start.dt.tz_convert("America/New_York")
        d = d[~(et.dt.strftime("%H:%M").isin(["09:30", "10:00"]) & (et.dt.dayofweek < 5))].copy()
        d["mn"] = d.start.dt.minute
        yes_dog = d.mid < 0.5
        fav_px = np.where(yes_dog, 1 - d.next_bid, d.next_ask)
        d["fav"] = 100 * (np.where(yes_dog, 1 - d.y, d.y) - fav_px) - 7 * fav_px * (1 - fav_px)
        v = d[(d.h == 840) & (d.rv_fut > 0)].copy()
        v["lv"] = np.log(v.rv_fut); v["lv"] -= v.groupby("month").lv.transform("mean")
        print(f"\n===== {s}")
        print("vol by start minute:", v.groupby("mn").lv.mean().round(3).to_dict())
        m = d[d.iv.notna() & (d.iv > 0) & (d.rv_fut > 0) & d.mid.between(0.1, 0.9)].copy()
        m["gap"] = np.log(m.iv / m.rv_fut)
        for band in [(600, 840), (240, 480), (60, 180)]:
            x = m[m.h.between(*band)]
            g = x.groupby(["mn", "half"]).agg(gap=("gap", "median"), dog=("dog", "mean"), fav=("fav", "mean"),
                                              n=("dog", "size")).unstack("half")
            print(f"-- h {band}")
            print(g.round(2).to_string())


if __name__ == "__main__":
    main(sys.argv[1:] or ["KXETH15M", "KXSOL15M", "KXBTC15M"])
