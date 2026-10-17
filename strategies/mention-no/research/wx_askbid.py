"""Screening only: KXHIGH favourite bracket bought at the ask proxy (last taker-buy price) and tails sold at the bid proxy
(last taker-sell price), at fixed hours before close, net of the 0.07p(1-p) fee. Dev data."""
import sys, numpy as np, pandas as pd
R = sys.argv[1]; H = (30, 24, 18, 12, 8)
rows = []
for s in sys.argv[2:]:
    d = pd.read_parquet(f"{R}/{s}.parquet", columns=["t", "paid", "edge", "yes", "p", "market", "event", "close_ns"])
    won = (d.edge / 100 + d.paid).round(); d["out"] = np.where(d.yes, won, 1 - won)
    for mk, g in d.groupby("market", sort=False):
        g = g.sort_values("t"); t = g.t.values; cl = g.close_ns.iloc[0]; y = g.yes.values; p = g.p.values
        for h in H:
            j = np.searchsorted(t, cl - h * 3.6e12, side="right")
            if j == 0: continue
            lo = max(0, j - 400)
            ya = np.where(y[lo:j])[0]; na = np.where(~y[lo:j])[0]
            if len(ya) == 0 or len(na) == 0: continue
            ia, ib = lo + ya[-1], lo + na[-1]
            if t[j - 1] - t[min(ia, ib)] > 4 * 3.6e12: continue
            rows.append((s, g.event.iloc[0], mk, h, p[ia], p[ib], g.out.iloc[0], cl))
r = pd.DataFrame(rows, columns=["s", "ev", "m", "h", "ask", "bid", "out", "cl"])
r.to_parquet(f"{R}/wx_ab.parquet"); print(len(r))
