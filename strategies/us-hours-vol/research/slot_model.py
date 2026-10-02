"""Screen 4: generalise beyond 9:30. Forecast log rv_fut with HAR (+ rv_5m) plus either UTC-hour dummies
(eth-volfav style) or NY-clock 15-min slot dummies split weekday/weekend (+ an 'elapsed-in-slot' term via h).
Fit on Jan-Apr (A), test on May-Aug 19 (B). Then deciles of r = log iv - forecast (cut on A):
underdog PnL in low deciles, favourite PnL in high deciles, at next real fills after fee."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "strategies/us-hours-vol/research")
from iv_gap import load

def design(d, kind):
    cols = [np.ones(len(d)), np.log(d.rv_5m), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h), np.log(d.h)]
    if kind == "utc":
        cols += [(d.close.dt.hour == k).astype(float).values for k in range(1, 24)]
    else:
        slot = (d.et.dt.hour * 4 + d.et.dt.minute // 15).values + 96 * d.wkend.values
        # slot dummies interacted with early/late half of the window: the burst decays within the slot
        late = (d.h <= 420).values
        for k in range(1, 192):
            m = (slot == k)
            cols += [m.astype(float), (m & late).astype(float)]
    return np.column_stack(cols)

for s in sys.argv[1:] or ["KXETH15M", "KXSOL15M", "KXBTC15M"]:
    d = load(s)
    d = d[(d.rv_5m > 0) & (d.rv_15m > 0) & (d.rv_60m > 0) & (d.rv_4h > 0)].copy()
    A = d[d.half == "A"]
    print(f"\n===== {s}")
    for kind in ["utc", "ny"]:
        fa = A[A.rv_fut > 0]
        beta, *_ = np.linalg.lstsq(design(fa, kind), np.log(fa.rv_fut), rcond=None)
        d["f"] = design(d, kind) @ beta
        B = d[(d.half == "B") & (d.rv_fut > 0)]
        y = np.log(B.rv_fut)
        print(f"[{kind}] out-of-sample R2 on B: {1 - ((y - B.f) ** 2).mean() / y.var():.3f}")
        x = d[d.iv.notna() & (d.iv > 0) & np.minimum(d.mid, 1 - d.mid).between(0.10, 0.45)
              & d.next_ask.notna() & d.next_bid.notna() & d.h.between(60, 600)].copy()
        x["r"] = np.log(x.iv) - x.f
        cuts = x[x.half == "A"].r.quantile(np.linspace(0, 1, 11)).values
        x["dec"] = np.clip(np.searchsorted(cuts, x.r) - 1, 0, 9)
        t = x.groupby(["dec", "half"]).agg(dog=("dog", "mean"), fav=("fav", "mean"), n=("dog", "size")).unstack()
        print(t.round(2).to_string())
        lo = x[(x.dec == 0) & ~x.wkend]
        print("  bottom decile weekday rows by NY slot (top 6 by count):",
              lo.q.value_counts().head(6).to_dict())
