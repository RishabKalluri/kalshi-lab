"""Early-window screen: is a plain spot-distance model better than the market early in the window (h >= 480),
where our basis error is negligible relative to the remaining move?  Fit vol mix on half A, test on B.
    uv run python strategies/btc-anchor-vol/research/early_screen.py KXETH15M"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1]
d = pd.read_parquet(ROOT / "research/data" / f"{series}.parquet")
d = d[(d.close < "2026-08-20") & (d.rv_15m > 0) & (d.rv_60m > 0) & (d.rv_4h > 0) & (d.close >= "2026-01-15")].copy()
d = d[(d.K / d.S - 1).abs() < 0.05]
d["half"] = np.where(d.close < pd.Timestamp("2026-05-01", tz="UTC"), "A", "B")
d["month"] = d.close.dt.strftime("%m")
fee = lambda P: 0.07 * P * (1 - P)
ll = lambda p, y: -np.mean(y * np.log(np.clip(p, 1e-4, 1 - 1e-4)) + (1 - y) * np.log(np.clip(1 - p, 1e-4, 1 - 1e-4)))
def prob(g, k):
    s = k * np.exp((np.log(g.rv_15m) + np.log(g.rv_60m) + np.log(g.rv_4h)) / 3)
    return norm.cdf(g.D / (s * np.sqrt(g.h - 40)))
A = d[d.half == "A"]
ks = np.linspace(0.6, 1.6, 21)
k = ks[np.argmin([ll(prob(A, k), A.y) for k in ks])]
print(series, "vol scale k =", round(k, 2))
d["p"] = prob(d, k)
f = d.dropna(subset=["next_ask", "next_bid"])
print("h, log loss model / next-fill mid, n  (half B)")
for h, g in f[f.half == "B"].groupby("h"):
    print(f"  {h:4d} {ll(g.p, g.y):.4f} {ll((g.next_ask + g.next_bid) / 2, g.y):.4f} {len(g)}")
# trade: buy YES at next_ask if p - ask > thr + fee; NO if bid - p > thr + fee
out = []
for side in ["yes", "no"]:
    g = d.dropna(subset=["next_ask" if side == "yes" else "next_bid"]).copy()
    if side == "yes":
        g["edge"] = g.p - g.next_ask - fee(g.next_ask); g["pnl"] = (g.y - g.next_ask - fee(g.next_ask)) * 100
    else:
        g["edge"] = g.next_bid - g.p - fee(g.next_bid); g["pnl"] = ((1 - g.y) - (1 - g.next_bid) - fee(g.next_bid)) * 100
    out.append(g)
t = pd.concat(out)
t["eb"] = pd.cut(t.edge, [-1, 0, 0.03, 0.06, 0.1, 0.2, 1])
t["hb"] = pd.cut(t.h, [0, 200, 400, 650, 900])
print("\npnl c/ct by model edge x horizon, halves A|B (n)")
pv = t.pivot_table(index=["hb", "eb"], columns="half", values="pnl", aggfunc=["mean", "count"], observed=True)
print(pv.round(2).to_string())
sel = t[(t.edge > 0.06) & (t.h >= 480)]
print("edge>6c, h>=480 by month:", sel.groupby("month").pnl.agg(["mean", "count"]).round(2).T.to_string())
