"""H2 screen: a vol forecast that knows the clock (NY hour-of-week, quarter-of-hour, in-window decay via h) vs
volfav's HAR; fair prob from spot distance; edge vs next real fill on both sides. Fit on A (Dec-Apr), test B."""
import sys, numpy as np, pandas as pd
from scipy.stats import norm
pd.set_option("display.width", 220)
fee = lambda p: np.ceil(7 * p * (1 - p)) / 100

series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
d = pd.read_parquet(f"research/data/{series}.parquet")
d = d[(d.close < "2026-08-20")].dropna(subset=["rv_5m", "rv_15m", "rv_60m", "rv_4h"])
d = d[(d.rv_5m > 0) & (d.rv_15m > 0) & (d.rv_60m > 0) & (d.rv_4h > 0)].copy()
ny = d.close.dt.tz_convert("America/New_York")
start = ny - pd.Timedelta(minutes=15)
d["how"] = start.dt.dayofweek * 24 + start.dt.hour      # NY hour of week of the window start
d["qh"] = start.dt.minute // 15
d["utch"] = d.close.dt.hour
d["half"] = np.where(d.close < "2026-05-01", "A", "B")

def X(df, kind):
    cols = [np.ones(len(df)), np.log(df.rv_15m), np.log(df.rv_60m), np.log(df.rv_4h), np.log(df.h)]
    if kind == "har":
        cols += [(df.utch == k).astype(float) for k in range(1, 24)]
    else:
        cols += [np.log(df.rv_5m)]
        cols += [(df.how == k).astype(float) for k in range(1, 168)]
        cols += [(df.qh == k).astype(float) for k in range(1, 4)]
        cols += [np.log(df.h) * (df.qh == k) for k in range(1, 4)]
    return np.column_stack(cols)

A, B = d[d.half == "A"], d[d.half == "B"]
fitA = A[A.rv_fut > 0.02 * A.rv_fut.median()]
for kind in ["har", "clock"]:
    beta, *_ = np.linalg.lstsq(X(fitA, kind), np.log(fitA.rv_fut), rcond=None)
    d[f"fc_{kind}"] = np.exp(X(d, kind) @ beta)
    b = d[(d.half == "B") & (d.rv_fut > 0.02 * A.rv_fut.median())]
    res = np.log(b.rv_fut) - np.log(b[f"fc_{kind}"])
    print(kind, "OOS R2 on B:", round(1 - res.var() / np.log(b.rv_fut).var(), 4), "bias", round(res.mean(), 3))

# fair prob (settlement-average adjusted), calibrated by a logistic on z fit in A
from sklearn.linear_model import LogisticRegression
for kind in ["har", "clock"]:
    z = d.D / (d[f"fc_{kind}"] * np.sqrt(np.maximum(d.h - 40, 5)))
    d[f"z_{kind}"] = z
    lr = LogisticRegression().fit(np.column_stack([z[d.half == "A"]]), d.y[d.half == "A"])
    d[f"p_{kind}"] = lr.predict_proba(np.column_stack([z]))[:, 1]
    # edge on each side at the next real fill
    by = d[f"p_{kind}"] - d.next_ask - fee(d.next_ask)          # buy YES
    sy = (1 - d[f"p_{kind}"]) - (1 - d.next_bid) - fee(1 - d.next_bid)  # buy NO
    pnl_b = (d.y - d.next_ask - fee(d.next_ask)) * 100
    pnl_s = ((1 - d.y) - (1 - d.next_bid) - fee(1 - d.next_bid)) * 100
    rows = []
    for e, pnl, side in [(by, pnl_b, "yes"), (sy, pnl_s, "no")]:
        rows.append(pd.DataFrame({"edge": e * 100, "pnl": pnl, "half": d.half, "h": d.h, "mid": d.mid}))
    r = pd.concat(rows).dropna()
    r = r[r.h.between(60, 840) & (r.edge > -50)]
    r["eb"] = pd.cut(r.edge, [-50, -4, -2, 0, 1, 2, 3, 4, 6, 10, 50])
    t = r.groupby(["eb", "half"], observed=True).pnl.agg(["mean", "count"]).unstack()
    print(f"\n{series} {kind}: realized c/ct at next fill by model edge (c)\n", t.round(2).to_string())
    # model vs market log loss on B
    bb = d[(d.half == "B") & d.h.between(60, 840)].dropna(subset=[f"p_{kind}"])
    ll = lambda p: -np.mean(bb.y * np.log(np.clip(p, 1e-3, 1 - 1e-3)) + (1 - bb.y) * np.log(np.clip(1 - p, 1e-3, 1 - 1e-3)))
    print("log loss B: model", round(ll(bb[f"p_{kind}"]), 4), "market mid", round(ll(bb.mid), 4))

# --- H2b: does the clock-vol model add information beyond the market price? logistic on [logit(mid), z_clock]
print("\n=== H2b: market + model combined ===")
lm = np.log(d.mid.clip(0.01, 0.99) / (1 - d.mid.clip(0.01, 0.99)))
d["lm"] = lm
d["sgn_lr"] = np.sign(lm) * np.log((d.iv / d.fc_clock).clip(0.05, 20)).fillna(0)
F = lambda df: np.column_stack([df.lm, df.z_clock.clip(-8, 8), df.sgn_lr])
ok = d.h.between(60, 840) & d.mid.between(0.03, 0.97)
tr = d[ok & (d.half == "A")]
lr = LogisticRegression(C=10).fit(F(tr), tr.y)
print("coef [logit mid, z_clock, sign*log(iv/fc)]:", lr.coef_.round(3), lr.intercept_.round(3))
te = d[ok].copy()
te["pc"] = lr.predict_proba(F(te))[:, 1]
by = te.pc - te.next_ask - fee(te.next_ask); sy = te.next_bid - te.pc - fee(1 - te.next_bid)
pb = (te.y - te.next_ask - fee(te.next_ask)) * 100; ps = (te.next_bid - te.y - fee(1 - te.next_bid)) * 100
r = pd.concat([pd.DataFrame({"edge": by * 100, "pnl": pb, "half": te.half, "side": "yes"}),
               pd.DataFrame({"edge": sy * 100, "pnl": ps, "half": te.half, "side": "no"})]).dropna()
r["eb"] = pd.cut(r.edge, [-50, -2, 0, 1, 2, 3, 4, 6, 50])
print(r.groupby(["eb", "half"], observed=True).pnl.agg(["mean", "count"]).unstack().round(2).to_string())
