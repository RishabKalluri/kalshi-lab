"""Screen: does BTC's Kalshi implied vol (scaled by the coin/BTC vol ratio) forecast the coin's vol better than HAR,
and does ETH/SOL implied vol relative to that anchored forecast pick mispriced sides at real next fills?

    uv run python strategies/btc-anchor-vol/research/anchor_screen.py KXETH15M
Development data only (research/data/*.parquet stop at the lockbox). Fit on Jan-Apr (half A), test May-Aug 19 (B).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1]
H = [360, 300, 240, 180, 120, 90, 60]
c = pd.read_parquet(ROOT / "research/data" / f"{series}.parquet")
b = pd.read_parquet(ROOT / "research/data/KXBTC15M.parquet")
c = c[(c.close < "2026-08-20") & c.h.isin(H)]
b = b[(b.close < "2026-08-20") & b.h.isin(H)]
b = b[["close", "h", "iv", "mid", "rv_15m", "rv_60m", "rv_4h", "rv_fut", "next_ask", "next_bid"]].add_prefix("b_")
d = c.merge(b, left_on=["close", "h"], right_on=["b_close", "b_h"], how="left")
d = d[(d.rv_15m > 0) & (d.rv_60m > 0) & (d.rv_4h > 0) & (d.b_rv_60m > 0) & (d.b_rv_4h > 0)].copy()
d = d[d.close >= "2026-01-15"]  # SOL starts Jan 9; need 4h history and a common start
d["half"] = np.where(d.close < pd.Timestamp("2026-05-01", tz="UTC"), "A", "B")
d["month"] = d.close.dt.strftime("%m")
print(f"{series}: {d.ticker.nunique()} markets, {len(d)} rows; BTC iv defined in {d.b_iv.notna().mean():.0%} of rows")

# --- 1. vol forecasting: target log rv_fut (coin), features
d["lr15"], d["lr60"], d["lr4h"], d["lh"] = np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h), np.log(d.h)
d["lratio60"] = np.log(d.rv_60m / d.b_rv_60m)
d["lratio4h"] = np.log(d.rv_4h / d.b_rv_4h)
d["lbiv"] = np.log(d.b_iv)
d["lbrv15"] = np.log(d.b_rv_15m)
fitset = d[(d.rv_fut > 0) & d.lbiv.notna() & np.isfinite(d.lbiv)].copy()
fitset = fitset[fitset.rv_fut > fitset.rv_fut.quantile(0.01)]
fitset["y"] = np.log(fitset.rv_fut)
SPECS = {
    "HAR": ["lr15", "lr60", "lr4h", "lh"],
    "HAR+btc_iv": ["lr15", "lr60", "lr4h", "lh", "lbiv"],
    "btc_iv+ratio": ["lbiv", "lratio4h", "lratio60", "lh"],
    "HAR+btc_iv+ratio": ["lr15", "lr60", "lr4h", "lh", "lbiv", "lratio4h"],
}
betas = {}
for name, cols in SPECS.items():
    A, B = fitset[fitset.half == "A"], fitset[fitset.half == "B"]
    XA = np.column_stack([np.ones(len(A))] + [A[c] for c in cols])
    XB = np.column_stack([np.ones(len(B))] + [B[c] for c in cols])
    beta, *_ = np.linalg.lstsq(XA, A.y, rcond=None)
    betas[name] = (cols, beta)
    res = B.y - XB @ beta
    r2 = 1 - res.var() / B.y.var()
    print(f"  {name:18s} out-of-sample R2 {r2:.3f}  beta {np.round(beta, 3).tolist()}")

# --- 2. trading signal: coin iv / forecast; favourite PnL at next real fill by decile, per half
fee = lambda P: 0.07 * P * (1 - P)
t = d.dropna(subset=["iv"]).copy()
t = t[t.lbiv.notna() & np.isfinite(t.lbiv)]
fav_yes = t.mid > 0.5
pf = np.where(fav_yes, t.next_ask, 1 - t.next_bid)          # buy favourite
pu = np.where(fav_yes, 1 - t.next_bid, t.next_ask)           # buy underdog
wf = np.where(fav_yes, t.y, 1 - t.y)
t["fav_pnl"] = (wf - pf - fee(pf)) * 100
t["dog_pnl"] = ((1 - wf) - pu - fee(pu)) * 100
for name in ["HAR", "HAR+btc_iv+ratio", "btc_iv+ratio"]:
    cols, beta = betas[name]
    X = np.column_stack([np.ones(len(t))] + [t[c] for c in cols])
    t["sig_" + name] = np.log(t.iv) - X @ beta
for name in ["HAR", "HAR+btc_iv+ratio", "btc_iv+ratio"]:
    s = t["sig_" + name]
    edges = s[t.half == "A"].quantile(np.linspace(0, 1, 11)).values.copy()
    edges[0], edges[-1] = -np.inf, np.inf
    t["dec"] = pd.cut(s, edges, labels=False)
    print(f"\n== signal log(iv) - forecast [{name}], deciles from half A")
    rows = []
    for dec, g in t.groupby("dec"):
        r = dict(dec=int(dec))
        for half in "AB":
            gh = g[g.half == half]
            r[f"fav_{half}"] = gh.fav_pnl.mean()
            r[f"dog_{half}"] = gh.dog_pnl.mean()
            r[f"n_{half}"] = gh.fav_pnl.notna().sum()
        rows.append(r)
    print(pd.DataFrame(rows).round(2).to_string(index=False))
    top = t[t.dec >= 7]
    print("  top 30% favourite by month:", top.groupby("month").fav_pnl.mean().round(2).to_dict())
    bot = t[t.dec <= 1]
    print("  bottom 20% underdog by month:", bot.groupby("month").dog_pnl.mean().round(2).to_dict())
    t[f"top_{name}"] = t.dec >= 7
print("\noverlap of top-30% sets, HAR vs HAR+btc_iv+ratio:",
      (t["top_HAR"] & t["top_HAR+btc_iv+ratio"]).sum() / max(t["top_HAR+btc_iv+ratio"].sum(), 1))
only = t[t["top_HAR+btc_iv+ratio"] & ~t["top_HAR"]]
print("anchored-only top rows: favourite pnl by half", only.groupby("half").fav_pnl.agg(["mean", "count"]).round(2).to_dict())
only = t[~t["top_HAR+btc_iv+ratio"] & t["top_HAR"]]
print("HAR-only top rows: favourite pnl by half", only.groupby("half").fav_pnl.agg(["mean", "count"]).round(2).to_dict())
