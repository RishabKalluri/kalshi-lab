import sys, numpy as np, pandas as pd
D = sys.argv[1]
def boot(g, n=300):
    a = g.assign(x=g.edge * g.c).groupby("event").agg(x=("x", "sum"), c=("c", "sum")); a = a[a.c > 0]
    if len(a) < 8: return np.nan, np.nan, np.nan, len(a)
    xs, cs = a.x.values, a.c.values; idx = np.random.default_rng(0).integers(0, len(a), (n, len(a))); m = xs[idx].sum(1) / cs[idx].sum(1)
    return xs.sum()/cs.sum(), *np.percentile(m, [2.5, 97.5]), len(a)
for s in sys.argv[2:]:
    df = pd.read_parquet(f"{D}/{s}.parquet", columns=["paid", "edge", "c", "yes", "event"])
    print(f"\n== {s}: {len(df)} trades, {df.event.nunique()} events, {df.c.sum()/1e3:.0f}k contracts; overall {boot(df)[0]:.2f}")
    for side, nm in ((True, "YES"), (False, "NO ")):
        d = df[df.yes == side]; row = []
        for lo, hi in ((0, .1), (.1, .3), (.3, .5), (.5, .7), (.7, .9), (.9, 1.0)):
            g = d[(d.paid > lo) & (d.paid <= hi)]
            e, l, h, n = boot(g) if len(g) else (np.nan,) * 4
            row.append(f"{lo:.1f}-{hi:.1f}: {e:6.1f}[{l:5.1f},{h:5.1f}] {g.c.sum()/1e3:6.0f}k")
        print(nm, " | ".join(row))
