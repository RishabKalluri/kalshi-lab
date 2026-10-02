"""Screen 1: is crypto 15-min vol shaped by US hours? Per-window realized vol (rv_fut at h=840) by
window start time in UTC vs New York time, before/after the Mar 8 2026 DST change, weekday vs weekend.
Development data only (the parquet stops at the lockbox)."""
import sys
import numpy as np, pandas as pd
from kalshi_lab.validate import LOCKBOX_START

for s in sys.argv[1:] or ["KXETH15M", "KXSOL15M", "KXBTC15M"]:
    d = pd.read_parquet(f"research/data/{s}.parquet")
    d = d[(d.close < pd.Timestamp(LOCKBOX_START)) & (d.h == 840) & (d.rv_fut > 0)].copy()
    d["start"] = d.close - pd.Timedelta(minutes=15)
    d["et"] = d.start.dt.tz_convert("America/New_York")
    d["dst"] = d.et.map(lambda x: bool(x.dst()))
    d["wkend"] = d.et.dt.dayofweek >= 5
    d["lv"] = np.log(d.rv_fut / d.S)  # relative vol so price level doesn't matter
    d["lv"] -= d.groupby(d.start.dt.to_period("M").astype(str)).lv.transform("mean")  # remove monthly level
    wd = d[~d.wkend]
    print(f"\n=== {s}: {len(d)} windows. log vol vs monthly mean, weekdays, by window start (30-min bins) ===")
    wd = wd.assign(utc=wd.start.dt.hour + wd.start.dt.minute // 30 / 2, nyc=wd.et.dt.hour + wd.et.dt.minute // 30 / 2)
    t = pd.DataFrame({
        "UTC_EST": wd[~wd.dst].groupby("utc").lv.mean(), "UTC_EDT": wd[wd.dst].groupby("utc").lv.mean(),
        "NY_EST": wd[~wd.dst].groupby("nyc").lv.mean(), "NY_EDT": wd[wd.dst].groupby("nyc").lv.mean()})
    print(t.round(2).to_string())
    # which clock explains the shape better: correlation of EST vs EDT profiles in each clock
    print("corr EST vs EDT profile, UTC clock: %.3f   NY clock: %.3f" % (t.UTC_EST.corr(t.UTC_EDT), t.NY_EST.corr(t.NY_EDT)))
    we = d.groupby("wkend").lv.mean()
    print("weekend vs weekday mean log vol: %.2f (x%.2f)" % (we[True] - we[False], np.exp(we[True] - we[False])))
    # 15-min resolution around US open, NY clock, weekdays
    wd = wd.assign(q=wd.et.dt.strftime("%H:%M"))
    q = wd.groupby("q").lv.agg(["mean", "count"])
    print("NY 15-min windows 07:00-11:00 and 15:00-17:00:")
    print(q.loc[[x for x in q.index if "07:00" <= x <= "11:00" or "15:00" <= x <= "17:00"]].round(2).T.to_string())
