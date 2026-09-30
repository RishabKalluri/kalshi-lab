"""Where does a run's PnL come from? For each fill:
  edge     = how far inside the mid we traded (+ = bought below mid / sold above)
  adverse  = mid move over the next N seconds, in our direction (- = picked off)
  carry    = everything after that: holding inventory to settlement
Needs a run with timeline.csv.gz.   uv run python scripts/decompose.py results/<run> [N=30]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd

run = Path(sys.argv[1])
n = int(sys.argv[2]) if len(sys.argv) > 2 else 30
fills = pd.read_csv(run / "fills.csv", parse_dates=["time"])
mk = pd.read_csv(run / "markets.csv")
tl = pd.read_csv(run / "timeline.csv.gz", parse_dates=["time"])
tl["mid"] = (tl.bid + tl.ask) / 2
res = dict(zip(mk.ticker, mk.result))
rows = []
for tk, f in fills.groupby("ticker"):
    t = tl[tl.ticker == tk].dropna(subset=["mid"]).sort_values("time")
    if t.empty or tk not in res:
        continue
    times = t.time.values
    for _, r in f.iterrows():
        sign = 1 if r.side == "buy" else -1
        i0 = max(0, np.searchsorted(times, r.time.to_datetime64(), side="right") - 1)
        i1 = min(len(t) - 1, np.searchsorted(times, (r.time + pd.Timedelta(seconds=n)).to_datetime64(), side="right") - 1)
        m0, m1 = t.mid.iloc[i0], t.mid.iloc[i1]
        settle = 1000 if res[tk] == "yes" else 0
        rows.append(dict(ticker=tk, qty=r.qty, edge=sign * (m0 - r.price), adverse=sign * (m1 - m0),
                         carry=sign * (settle - m1), fee=r.fee, side=r.side))
d = pd.DataFrame(rows)
tot = lambda c: (d[c] * d.qty).sum() / 1000
print(f"{run.name}: {len(d)} fills, {d.qty.sum():,.0f} contracts, {d.ticker.nunique()} markets")
print(f"  edge vs mid at fill   {tot('edge'):+9.2f}   ({tot('edge') / d.qty.sum() * 100:+.2f}c/contract)")
print(f"  adverse, next {n}s     {tot('adverse'):+9.2f}   ({tot('adverse') / d.qty.sum() * 100:+.2f}c/contract)")
print(f"  carry to settlement   {tot('carry'):+9.2f}   ({tot('carry') / d.qty.sum() * 100:+.2f}c/contract)")
print(f"  fees                  {-d.fee.sum():+9.2f}")
print(f"  total                 {tot('edge') + tot('adverse') + tot('carry') - d.fee.sum():+9.2f}"
      f"   (reported pnl {mk.pnl.sum():+.2f}; timeline is 5s-sampled so this is approximate)")
