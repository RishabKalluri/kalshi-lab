"""H1 screen: are the Tokyo / Shanghai-HK / London equity opens vol steps the Kalshi price misses?
Each open is tested on its own local clock. For the window that starts at the open and its neighbours:
  vol: mean log(rv_fut at h=840) minus the month's weekday mean (how much more vol than usual),
  gap: median log(iv / rv_fut) mid-window (h 240-480) (market vol vs realized; lower = vol underpriced),
  dog: underdog PnL (c/ct) at the next real fill after the taker fee, mid window, halves A (<May) / B (May-Aug 19),
on local weekdays, and the same clock time on local weekends as a placebo. Development data only."""
import sys
import numpy as np, pandas as pd
from kalshi_lab.validate import LOCKBOX_START

CLOCKS = {"tokyo": "Asia/Tokyo", "hk": "Asia/Hong_Kong", "london": "Europe/London", "ny": "America/New_York"}
OPENS = {"tokyo": "09:00", "hk": "09:30", "london": "08:00", "ny": "09:30"}


def load(s):
    d = pd.read_parquet(f"research/data/{s}.parquet")
    d = d[d.close < pd.Timestamp(LOCKBOX_START)].copy()
    d["start"] = d.close - pd.Timedelta(minutes=15)
    d["half"] = np.where(d.close < pd.Timestamp("2026-05-01", tz="UTC"), "A", "B")
    d["month"] = d.close.dt.strftime("%Y-%m")
    yes_dog = d.mid < 0.5
    dog_px = np.where(yes_dog, d.next_ask, 1 - d.next_bid)
    dog_win = np.where(yes_dog, d.y, 1 - d.y)
    fee = lambda p: 7 * p * (1 - p)
    d["dog"] = 100 * (dog_win - dog_px) - fee(dog_px)
    return d


def slots_around(t, n=3):
    base = pd.Timestamp("2000-01-01 " + t)
    return [(base + pd.Timedelta(minutes=15 * k)).strftime("%H:%M") for k in range(-n, n + 1)]


def main(series):
    for s in series:
        d = load(s)
        # vol level per window (h=840 row), demeaned by month over all windows
        v = d[d.h == 840].copy()
        v = v[v.rv_fut > 0]
        v["lv"] = np.log(v.rv_fut)
        v["lv"] -= v.groupby("month").lv.transform("mean")
        m = d[d.h.between(240, 480) & d.iv.notna() & (d.iv > 0) & (d.rv_fut > 0) & d.mid.between(0.1, 0.9)].copy()
        m["gap"] = np.log(m.iv / m.rv_fut)
        print(f"\n===== {s}  (all-window median gap {m.gap.median():.2f}, dog A {m[m.half=='A'].dog.mean():.2f} "
              f"B {m[m.half=='B'].dog.mean():.2f})")
        for name, tz in CLOCKS.items():
            for x in (v, m):
                loc = x.start.dt.tz_convert(tz)
                x["q"] = loc.dt.strftime("%H:%M")
                x["wk"] = loc.dt.dayofweek < 5
            rows = []
            for q in slots_around(OPENS[name]):
                for wk in (True, False):
                    vv = v[(v.q == q) & (v.wk == wk)]
                    mm = m[(m.q == q) & (m.wk == wk)]
                    a, b = mm[mm.half == "A"].dog, mm[mm.half == "B"].dog
                    rows.append(dict(slot=q, days="wkday" if wk else "wkend", vol=vv.lv.mean(), gap=mm.gap.median(),
                                     dogA=a.mean(), seA=a.std() / max(1, len(a)) ** .5, dogB=b.mean(),
                                     seB=b.std() / max(1, len(b)) ** .5, n=len(mm)))
            print(f"-- {name} clock (open {OPENS[name]} local)")
            print(pd.DataFrame(rows).round(2).to_string(index=False))


if __name__ == "__main__":
    main(sys.argv[1:] or ["KXETH15M", "KXSOL15M", "KXBTC15M"])
