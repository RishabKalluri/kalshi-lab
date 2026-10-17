"""Weather: taker edge by side x price band x local-time bucket (maker = the other side). Screening."""
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
    df = pd.read_parquet(f"{D}/{s}.parquet", columns=["t","paid","edge","c","yes","event","mk300"])
    tz = ZoneInfo(tz_for(s))
    st = {e: pd.Timestamp(day_of(e), tz=tz).value for e in df.event.unique()}
    df["h"] = (df.t - df.event.map(st)) / 3.6e12
    df["city"] = s
    df["event"] = s + df.event
    fr.append(df.drop(columns="t"))
df = pd.concat(fr, ignore_index=True)
df["hb"] = pd.cut(df.h, [-100, 0, 8, 14, 20, 100], labels=["prior-day", "00-08", "08-14", "14-20", "20+"])
df["pb"] = pd.cut(df.paid, [0, .03, .08, .15, .3, .5, .7, .85, .95, 1.0])
def boot(g, n=300):
    a = g.assign(x=g.edge * g.c).groupby("event").agg(x=("x", "sum"), c=("c", "sum")); a = a[a.c > 0]
    if len(a) < 20: return np.nan, np.nan, np.nan, len(a)
    xs, cs = a.x.values, a.c.values
    idx = np.random.default_rng(0).integers(0, len(a), (n, len(a)))
    m = xs[idx].sum(1) / cs[idx].sum(1)
    return xs.sum() / cs.sum(), *np.percentile(m, [2.5, 97.5]), len(a)
for side, name in ((True, "YES takers (maker sells YES)"), (False, "NO takers (maker buys YES)")):
    print("\n==", name, "taker edge c/ct [CI], contracts k, city-days")
    d = df[df.yes == side]
    for k, g in d.groupby("pb", observed=True):
        e, lo, hi, n = boot(g)
        row = " | ".join(f"{h}:{boot(gg, 100)[0]:5.1f}" for h, gg in g.groupby("hb", observed=True))
        print(f"{k!s:12} {e:6.2f} [{lo:6.2f},{hi:6.2f}] {g.c.sum()/1e3:8.0f}k n={n:5d} || {row}")
