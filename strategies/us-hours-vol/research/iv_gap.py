"""Screen 2: does the Kalshi price anticipate the scheduled US-hours vol steps?
By NY 15-min window (weekdays), mean log(iv/rv_fut) (market vs realized), log(iv/rv_15m) (market vs trailing),
and underdog / favourite PnL at the next real fill after the taker fee, in both halves (A: <May, B: May-Aug 19)."""
import sys
import numpy as np, pandas as pd
from kalshi_lab.validate import LOCKBOX_START

def load(s):
    d = pd.read_parquet(f"research/data/{s}.parquet")
    d = d[d.close < pd.Timestamp(LOCKBOX_START)].copy()
    d["start"] = d.close - pd.Timedelta(minutes=15)
    d["et"] = d.start.dt.tz_convert("America/New_York")
    d["q"] = d.et.dt.strftime("%H:%M")
    d["wkend"] = d.et.dt.dayofweek >= 5
    d["half"] = np.where(d.close < pd.Timestamp("2026-05-01", tz="UTC"), "A", "B")
    # underdog / favourite fills at next real trade
    yes_dog = d.mid < 0.5
    dog_px = np.where(yes_dog, d.next_ask, 1 - d.next_bid)
    dog_win = np.where(yes_dog, d.y, 1 - d.y)
    fav_px = np.where(yes_dog, 1 - d.next_bid, d.next_ask)
    fee = lambda p: 7 * p * (1 - p)
    d["dog"] = 100 * (dog_win - dog_px) - fee(dog_px)
    d["fav"] = 100 * ((1 - dog_win) - fav_px) - fee(fav_px)
    return d

if __name__ == "__main__":
    for s in sys.argv[1:] or ["KXETH15M", "KXSOL15M", "KXBTC15M"]:
        d = load(s)
        w = d[~d.wkend & d.iv.notna() & (d.iv > 0) & (d.rv_fut > 0) & (d.rv_15m > 0)
              & (d.mid.between(0.1, 0.9))].copy()
        w["g_fut"] = np.log(w.iv / w.rv_fut)
        w["g_tr"] = np.log(w.iv / w.rv_15m)
        w["g_tf"] = np.log(w.rv_15m / w.rv_fut)
        print(f"\n=== {s} weekdays, rows with iv, mid 10-90c ===")
        print("overall median log(iv/rv_fut) %.2f, log(iv/rv_15m) %.2f" % (w.g_fut.median(), w.g_tr.median()))
        keep = [x for x in sorted(w.q.unique()) if "07:30" <= x <= "11:00" or "15:30" <= x <= "17:00" or x in ("20:00", "02:00")]
        for hs, hlab in [((600, 840), "early h600-840"), ((240, 480), "mid h240-480"), ((60, 180), "late h60-180")]:
            x = w[w.h.between(*hs)]
            g = x.groupby("q").agg(fut=("g_fut", "median"), trail=("g_tr", "median"), trail_vs_fut=("g_tf", "median"),
                                   dogA=("dog", lambda v: v[x.loc[v.index, "half"] == "A"].mean()),
                                   dogB=("dog", lambda v: v[x.loc[v.index, "half"] == "B"].mean()),
                                   favA=("fav", lambda v: v[x.loc[v.index, "half"] == "A"].mean()),
                                   favB=("fav", lambda v: v[x.loc[v.index, "half"] == "B"].mean()), n=("dog", "size"))
            g.loc["ALL"] = [x.g_fut.median(), x.g_tr.median(), x.g_tf.median(), x[x.half == "A"].dog.mean(),
                            x[x.half == "B"].dog.mean(), x[x.half == "A"].fav.mean(), x[x.half == "B"].fav.mean(), len(x)]
            print(f"-- {hlab}")
            print(g.loc[keep + ["ALL"]].round(2).to_string())
