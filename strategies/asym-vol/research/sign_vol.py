"""H1 screen: does future vol depend on the sign of the recent move, and does Kalshi price it? Dev data only.

    uv run python strategies/asym-vol/research/sign_vol.py [SERIES]

1) OLS of log rv_fut (t -> close) on log rv_5m/15m/60m/4h, |z15| and z15 signed (z15 = 15-min Binance return in
   rv_60m units), by half (A = Jan-Apr, B = May-Aug 19), h >= 300.
2) median log(iv/rv_fut) by z15 bin (does the market's vol vary with sign the way realized vol does?).
3) PnL per contract at next real fills after fee: buy YES (next_ask) / sell YES (next_bid) by z15 bin and h group.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
coin = series[2:5].lower()
z = np.load(ROOT / f"research/data/eth-overreact/binance_{coin}usdt.npz")
T0, spot = int(z["t0"]), z["px"]
d = pd.read_parquet(ROOT / f"research/data/{series}.parquet")
d = d[d.close < "2026-08-20"].copy()
t = (d.close.astype("int64") // 10**3 - d.h).to_numpy()  # ms -> s
ia = t - T0
ok = (ia - 4 * 3600 >= 0) & (ia < len(spot))
d = d[ok].copy(); ia = ia[ok]
for L in (300, 900, 3600):
    d[f"r{L}"] = spot[ia] - spot[ia - L]
d["z5"] = d.r300 / (d.rv_60m * np.sqrt(300))
d["z15"] = d.r900 / (d.rv_60m * np.sqrt(900))
d["z60"] = d.r3600 / (d.rv_60m * np.sqrt(3600))
d["half"] = np.where(d.close < "2026-05-01", "A", "B")
fee = lambda p: 0.07 * p * (1 - p)
d["pnl_buy"] = 100 * (d.y - d.next_ask - fee(d.next_ask))
d["pnl_sell"] = 100 * (d.next_bid - d.y - fee(d.next_bid))
print(series, len(d), "rows")

# 1) regression
r = d[(d.h >= 300) & (d.rv_fut > 0) & (d.rv_5m > 0) & (d.rv_15m > 0)].copy()
r["lf"] = np.log(r.rv_fut)
X = ["l5", "l15", "l60", "l4h", "az15", "z15", "az60", "z60"]
r["l5"], r["l15"], r["l60"], r["l4h"] = np.log(r.rv_5m), np.log(r.rv_15m), np.log(r.rv_60m), np.log(r.rv_4h)
r["az15"], r["az60"] = r.z15.abs(), r.z60.abs()
print("\n1) log rv_fut ~ HAR + |z| + signed z  (coef, t with per-market clustering ignored; markets overlap little at fixed h)")
for half, g in r.groupby("half"):
    g = g[g.h == 600]  # one row per market
    A = np.column_stack([np.ones(len(g))] + [g[c] for c in X])
    b, *_ = np.linalg.lstsq(A, g.lf, rcond=None)
    res = g.lf - A @ b
    cov = np.linalg.inv(A.T @ A) * res.var()
    tt = b / np.sqrt(np.diag(cov))
    print(half, len(g), " ".join(f"{c}={b[i+1]:+.3f}(t{tt[i+1]:+.1f})" for i, c in enumerate(X)))

# 2) market iv vs realized by signed z15
d["bin"] = pd.cut(d.z15, [-np.inf, -2, -1, -0.3, 0.3, 1, 2, np.inf])
m = d[(d.iv > 0) & (d.rv_fut > 0) & d.mid.between(0.1, 0.9) & (d.h.between(240, 720))].copy()
m["gap"] = np.log(m.iv / m.rv_fut)
m["gap_tr"] = np.log(m.iv / m.rv_15m)
print("\n2) median log(iv/rv_fut) and log(iv/rv_15m) by z15 bin, h 240-720, mid 10-90")
print(m.groupby(["bin", "half"], observed=True).agg(n=("gap", "size"), iv_fut=("gap", "median"),
      iv_tr=("gap_tr", "median"), rvf_rv15=("rv_fut", "median")).unstack("half").round(3).to_string())

# 3) PnL by sign bin and h group (first-of-each-market not enforced; rows overlap within a market)
d["hg"] = pd.cut(d.h, [0, 150, 330, 610, 900], labels=["60-120", "180-300", "360-600", "720-840"])
q = d[d.mid.between(0.05, 0.95)]
print("\n3) PnL c/contract: buy YES / sell YES at next fill after fee, by z15 bin x h group")
t3 = q.groupby(["hg", "bin", "half"], observed=True).agg(buy=("pnl_buy", "mean"), nb=("pnl_buy", "count"),
      sell=("pnl_sell", "mean"), ns=("pnl_sell", "count")).unstack("half").round(2)
print(t3.to_string())
