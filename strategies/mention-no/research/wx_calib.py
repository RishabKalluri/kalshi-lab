"""Screening only (dev data): KXHIGH price at fixed hours-to-close vs outcome, by bracket rank within the event.
Last trade at/before close-h. Input: screen.py parquets."""
import sys, os, numpy as np, pandas as pd
R = sys.argv[1]; H = (30, 24, 18, 12, 8, 4)
rows = []
for s in sys.argv[2:]:
    d = pd.read_parquet(f"{R}/{s}.parquet", columns=["t", "paid", "edge", "c", "yes", "p", "market", "event", "close_ns"])
    won = (d.edge / 100 + d.paid).round(); d["out"] = np.where(d.yes, won, 1 - won)
    for mk, g in d.groupby("market", sort=False):
        t = g.t.values; cl = g.close_ns.iloc[0]
        for h in H:
            j = np.searchsorted(t, cl - h * 3.6e12, side="right") - 1
            if j >= 0 and t[j] > cl - (h + 6) * 3.6e12:
                rows.append((s, g.event.iloc[0], mk, h, g.p.values[j], g.out.iloc[0], cl))
r = pd.DataFrame(rows, columns=["s", "ev", "m", "h", "p", "out", "cl"])
r.to_parquet(f"{R}/wx_fixed.parquet")
print(len(r))
