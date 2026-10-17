"""Sports taker edge by time-to-start proxy, ET hour, weekday, size, price. Screening only."""
import sys
import numpy as np
import pandas as pd
D, S, DUR = sys.argv[1], sys.argv[2], float(sys.argv[3])  # DUR: minutes from start to expected expiration
df = pd.read_parquet(f"{D}/{S}.parquet")
df["tts"] = (df.t - (df.exp_ns - int(DUR * 60e9))) / 3.6e12  # hours since estimated start (negative = pre-game)
et = pd.to_datetime(df.t, unit="ns", utc=True).dt.tz_convert("America/New_York")
df["hr"], df["dow"] = et.dt.hour, et.dt.dayofweek
def boot(g, col="edge", n=300):
    a = g.assign(x=g[col] * g.c).groupby("event").agg(x=("x", "sum"), c=("c", "sum")); a = a[a.c > 0]
    if len(a) < 5: return np.nan, np.nan, np.nan, len(a)
    xs, cs = a.x.values, a.c.values
    idx = np.random.default_rng(0).integers(0, len(a), size=(n, len(a)))
    m = xs[idx].sum(1) / cs[idx].sum(1)
    return xs.sum() / cs.sum(), np.percentile(m, 2.5), np.percentile(m, 97.5), len(a)
def mk(g, h):
    ok = g[f"mk{h}"].notna(); return np.nansum(g[f"mk{h}"] * g.c) / max(g.c[ok].sum(), 1)
def show(name, key):
    print(f"\n{S} by {name}\n{'bucket':14}{'ct(k)':>8}{'ev':>6}{'edge':>7}{'lo':>7}{'hi':>7}{'mk1':>7}{'mk5':>7}{'mk30':>7}{'mk60':>7}")
    for k, g in df.groupby(key, observed=True):
        e, lo, hi, n = boot(g)
        print(f"{k!s:14}{g.c.sum()/1e3:>8.0f}{n:>6}{e:>7.2f}{lo:>7.2f}{hi:>7.2f}" + "".join(f"{mk(g,h):>7.2f}" for h in (60,300,1800,3600)))
df["tb"] = pd.cut(df.tts, [-1e4,-48,-24,-12,-6,-3,-1,0,0.5,1,1.5,2,2.5,3,3.5,1e4])
show("hours since est. start", "tb")
df["hb"] = pd.cut(df.hr, [-1,5,9,12,15,18,21,23])
df["g"] = np.where(df.tts < 0, "pre", np.where(df.tts <= DUR/60, "ingame", "post"))
for ph in ("pre", "ingame"):
    sub = df[df.g == ph]; print("\n=== phase", ph)
    d0 = df; df = sub
    show("ET hour", "hb")
    df["wk"] = np.where(df.dow >= 5, "wkend", "wkday"); show("weekend", "wk")
    df["sz"] = pd.cut(df.c, [0,1,5,20,100,1e9]); show("size", "sz")
    df["pb"] = pd.cut(df.paid, [0,.05,.1,.2,.35,.5,.65,.8,.9,.95,1]); show("taker price", "pb")
    df = d0
