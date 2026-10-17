import sys
from datetime import datetime
from zoneinfo import ZoneInfo
import numpy as np, pandas as pd
sys.path.insert(0, ".")
from screen import tz_for
D = sys.argv[1]; SER = sys.argv[2:]
MONTH = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
def day_of(ev):
    s = ev.split("-")[1]; return datetime(2000 + int(s[:2]), MONTH[s[2:5]], int(s[5:]))
fr = []
for s in SER:
    df = pd.read_parquet(f"{D}/{s}.parquet", columns=["t","paid","edge","c","yes","event","p","mk300","mk1800","mk3600"])
    tz = ZoneInfo(tz_for(s))
    st = {e: pd.Timestamp(day_of(e), tz=tz).value for e in df.event.unique()}
    df["h"] = (df.t - df.event.map(st)) / 3.6e12
    df["city"] = s[5:]; df["mon"] = pd.to_datetime(df.t, unit="ns").dt.strftime("%m")
    df["event"] = s + df.event
    fr.append(df[(df.yes) & (df.paid > .02) & (df.paid <= .25) & (df.h > 10)].drop(columns="t"))
df = pd.concat(fr, ignore_index=True)
def boot(g, col="edge", n=400):
    a = g.assign(x=g[col] * g.c).groupby("event").agg(x=("x", "sum"), c=("c", "sum")); a = a[a.c > 0]
    if len(a) < 20: return np.nan, np.nan, np.nan, len(a)
    xs, cs = a.x.values, a.c.values
    idx = np.random.default_rng(0).integers(0, len(a), (n, len(a)))
    m = xs[idx].sum(1) / cs[idx].sum(1)
    return xs.sum() / cs.sum(), *np.percentile(m, [2.5, 97.5]), len(a)
df["hb"] = pd.cut(df.h, [10, 14, 17, 19, 21, 23, 25, 40])
print("YES takers paying 2-25c, by local hour of market day (h>10)")
for k, g in df.groupby("hb", observed=True):
    e, lo, hi, n = boot(g)
    print(f"{k!s:10} edge {e:6.2f} [{lo:6.2f},{hi:6.2f}] {g.c.sum()/1e3:7.0f}k ev={n} avgpx {np.average(g.paid, weights=g.c)*100:.1f} mk30 {np.nansum(g.mk1800*g.c)/g.c[g.mk1800.notna()].sum():.2f}")
late = df[df.h >= 19]
print("\nlate (h>=19) by city"); 
for k, g in late.groupby("city"):
    e, lo, hi, n = boot(g); print(f"{k:6} {e:6.2f} [{lo:6.2f},{hi:6.2f}] {g.c.sum()/1e3:7.0f}k ev={n}")
print("late by month")
for k, g in late.groupby("mon"):
    e, lo, hi, n = boot(g); print(f"{k:6} {e:6.2f} [{lo:6.2f},{hi:6.2f}] {g.c.sum()/1e3:7.0f}k ev={n}")
print("late by price")
for k, g in late.groupby(pd.cut(late.paid, [0.02, .05, .08, .12, .18, .25])):
    e, lo, hi, n = boot(g); print(f"{k!s:14} {e:6.2f} [{lo:6.2f},{hi:6.2f}] {g.c.sum()/1e3:7.0f}k ev={n}")
