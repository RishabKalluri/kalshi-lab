"""Weather taker edge by local hour relative to the market day, weekday, size, price. Screening only."""
import sys
from datetime import datetime
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd

sys.path.insert(0, ".")
from screen import tz_for  # noqa

D = sys.argv[1]
SER = sys.argv[2:]
MONTH = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def day_of(ev):
    s = ev.split("-")[1]
    return datetime(2000 + int(s[:2]), MONTH[s[2:5]], int(s[5:]))


def boot(g, col="edge", n=500):
    """contract-weighted mean with CI clustered by event."""
    a = g.assign(x=g[col] * g.c).groupby("event").agg(x=("x", "sum"), c=("c", "sum"))
    a = a[a.c > 0]
    if len(a) < 5:
        return np.nan, np.nan, np.nan, len(a)
    xs, cs = a.x.values, a.c.values
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(a), size=(n, len(a)))
    m = xs[idx].sum(1) / cs[idx].sum(1)
    return xs.sum() / cs.sum(), np.percentile(m, 2.5), np.percentile(m, 97.5), len(a)


frames = []
for s in SER:
    df = pd.read_parquet(f"{D}/{s}.parquet")
    tz = ZoneInfo(tz_for(s))
    evs = df.event.unique()
    start = {e: pd.Timestamp(day_of(e), tz=tz).value for e in evs}
    df["h"] = (df.t - df.event.map(start)) / 3.6e12  # hours since local midnight of the market day
    df["dow"] = df.event.map(lambda e: day_of(e).weekday())
    df["series"] = s
    frames.append(df)
df = pd.concat(frames, ignore_index=True)
print("trades", len(df), "contracts", int(df.c.sum()))
df["hb"] = pd.cut(df.h, [-100, -12, -6, 0, 4, 8, 11, 14, 17, 20, 24, 100],
                  labels=["<-12", "-12..-6", "-6..0", "0-4", "4-8", "8-11", "11-14", "14-17", "17-20", "20-24", ">24"])
df["wk"] = np.where(df.dow >= 5, "wkend", "wkday")
print("\nBy hour relative to local midnight of market day (all cities). taker edge c/ct [CI], markouts c")
print(f"{'bucket':10}{'ct(k)':>9}{'events':>7}{'edge':>8}{'lo':>7}{'hi':>7}{'mk1m':>7}{'mk5m':>7}{'mk30m':>7}{'mk60m':>7}")
for k, g in df.groupby("hb", observed=True):
    e, lo, hi, n = boot(g)
    mk = [np.nansum(g[f"mk{h}"] * g.c) / g.c[g[f"mk{h}"].notna()].sum() for h in (60, 300, 1800, 3600)]
    print(f"{k!s:10}{g.c.sum() / 1e3:>9.0f}{n:>7}{e:>8.2f}{lo:>7.2f}{hi:>7.2f}" + "".join(f"{x:>7.2f}" for x in mk))

print("\nPer city x hour bucket: edge (ct k)")
tab = {}
for (s, k), g in df.groupby(["series", "hb"], observed=True):
    e, lo, hi, n = boot(g, n=200)
    tab[(s, k)] = (e, lo, hi, g.c.sum() / 1e3)
for s in SER:
    print(s, " ".join(f"{k}:{tab[(s, k)][0]:.1f}({tab[(s, k)][3]:.0f}k)" for k in df.hb.cat.categories if (s, k) in tab))

print("\nWeekend vs weekday (all cities)")
for k, g in df.groupby("wk"):
    e, lo, hi, n = boot(g)
    print(k, f"{e:.2f} [{lo:.2f},{hi:.2f}] n={n}")
print("\nBy trade size")
df["sz"] = pd.cut(df.c, [0, 1, 5, 20, 100, 1e9], labels=["1", "2-5", "6-20", "21-100", ">100"])
for k, g in df.groupby("sz", observed=True):
    e, lo, hi, n = boot(g)
    mk = np.nansum(g.mk300 * g.c) / g.c[g.mk300.notna()].sum()
    print(f"{k!s:8}{g.c.sum() / 1e3:>9.0f}k  {e:.2f} [{lo:.2f},{hi:.2f}] mk5m {mk:.2f}")
print("\nBy taker price paid")
df["pb"] = pd.cut(df.paid, [0, .05, .15, .3, .5, .7, .85, .95, 1.0])
for k, g in df.groupby("pb", observed=True):
    e, lo, hi, n = boot(g)
    print(f"{k!s:12}{g.c.sum() / 1e3:>9.0f}k  {e:.2f} [{lo:.2f},{hi:.2f}]")
