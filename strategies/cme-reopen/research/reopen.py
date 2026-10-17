"""Screen: is the CME reopen (Sunday 18:00 ET; daily 18:00 ET) a vol step Kalshi misses?
Per NY weekday x slot around 18:00: vol (log rv_fut at h=840 minus month mean), gap (median log iv/rv_fut mid window),
underdog PnL at next real fill after fee (h 240-600, mid 0.1-0.9), halves A/B. Development data only."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "strategies/bell-vol/research")
from opens import load

for s in sys.argv[1:] or ["KXETH15M"]:
    d = load(s)
    v = d[(d.h == 840) & (d.rv_fut > 0)].copy()
    v["lv"] = np.log(v.rv_fut); v["lv"] -= v.groupby("month").lv.transform("mean")
    m = d[d.h.between(240, 600) & d.iv.notna() & (d.iv > 0) & (d.rv_fut > 0) & d.mid.between(0.1, 0.9)].copy()
    m["gap"] = np.log(m.iv / m.rv_fut)
    for x in (v, m):
        loc = x.start.dt.tz_convert("America/New_York")
        x["q"] = loc.dt.strftime("%H:%M"); x["dow"] = loc.dt.dayofweek
    print(f"\n===== {s} all: gap {m.gap.median():.2f} dogA {m[m.half=='A'].dog.mean():.2f} dogB {m[m.half=='B'].dog.mean():.2f}")
    rows = []
    for dow in (6, 5, 0, 2):
        for q in ["17:00", "17:30", "17:45", "18:00", "18:15", "18:30", "19:00"]:
            vv = v[(v.q == q) & (v.dow == dow)]
            # one checkpoint per market: first row in h 240-600 (largest h)
            mm = m[(m.q == q) & (m.dow == dow)].sort_values("h", ascending=False).drop_duplicates("ticker") if "ticker" in m else m[(m.q == q) & (m.dow == dow)]
            a, b = mm[mm.half == "A"].dog, mm[mm.half == "B"].dog
            rows.append(dict(dow=dow, slot=q, vol=vv.lv.mean(), gap=mm.gap.median(), dogA=a.mean(),
                             seA=a.std() / max(1, len(a)) ** .5, nA=len(a), dogB=b.mean(), seB=b.std() / max(1, len(b)) ** .5, nB=len(b)))
    print(pd.DataFrame(rows).round(2).to_string(index=False))
