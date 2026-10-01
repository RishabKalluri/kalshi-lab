"""Does flow add information beyond spot (model fair value) and the Kalshi price? And does it pay at real fills?
Reads screen_<SERIES>_<COIN>.parquet from flow_screen.py. Development data only."""
import sys
from pathlib import Path
from statistics import NormalDist

import numpy as np
import pandas as pd

SERIES = sys.argv[1] if len(sys.argv) > 1 else "KXSOL15M"
COIN = sys.argv[2] if len(sys.argv) > 2 else "eth"
d = pd.read_parquet(Path(__file__).parent / f"screen_{SERIES}_{COIN}.parquet")
N = NormalDist()
vol = d["rv_60m"].where(d["rv_60m"] > 0)
d["p_model"] = [N.cdf(x) if np.isfinite(x) else np.nan for x in d["D"] / (vol * np.sqrt(np.maximum(d["h"] - 40, 20)))]
d = d[np.isfinite(d.p_model) & d.mid.between(0.05, 0.95)].copy()
lg = lambda p: np.log(np.clip(p, .01, .99) / (1 - np.clip(p, .01, .99)))
d["l_mid"], d["l_mod"] = lg(d["mid"]), lg(d["p_model"])
d["month"] = d["close"].dt.strftime("%Y-%m")
flow = [c for c in d.columns if c.startswith(("okx_imb", "okx_sv", "bin_imb", "bin_sv"))]
rets = [c for c in d.columns if c.startswith(("own_ret", "okx_ret", "bin_ret"))]


def ols(X, y):
    X = np.column_stack([np.ones(len(X)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    e = y - X @ b
    cov = np.linalg.inv(X.T @ X) * (e @ e) / (len(y) - X.shape[1])
    return b, b / np.sqrt(np.diag(cov))


print(f"{SERIES}, {COIN} flow; n={len(d)} rows, {d.ticker.nunique()} markets")
base = ["l_mid", "l_mod"]
print("\nlinear prob: y ~ logit(mid) + logit(model) + [feature]  (t-stats; rows within a market are correlated, so discount ~sqrt(3))")
for f in flow + rets:
    z = d[base + [f]].copy(); z[f] = (z[f] - z[f].mean()) / z[f].std()
    b, tt = ols(z.values, d["y"].values.astype(float))
    print(f"  {f:12s} coef/sd {b[-1]*100:+.2f}pp  t={tt[-1]:+.1f}   (mid t={tt[1]:+.1f} model t={tt[2]:+.1f})")

# trading screen at real next fills: buy YES at next_ask if signal>q_hi, buy NO at (1-next_bid) if signal<q_lo
def fee(p):
    return 0.07 * p * (1 - p)


def trade(sig, label, q=0.9):
    tr, te = d.close < "2026-05-01", d.close >= "2026-05-01"
    hi, lo = sig[tr].quantile(q), sig[tr].quantile(1 - q)
    out = []
    for name, m in (("train", tr), ("test", te)):
        s = sig[m]; x = d[m]
        b = (s > hi) & x.next_ask.notna()
        a = (s < lo) & x.next_bid.notna()
        pb = x.y[b] - x.next_ask[b] - fee(x.next_ask[b])
        pa = (1 - x.y[a]) - (1 - x.next_bid[a]) - fee(x.next_bid[a])
        p = pd.concat([pb, pa])
        out.append(f"{name}: n={len(p)} {p.mean()*100:+.2f}c (se {p.std()/np.sqrt(len(p))*100:.2f})")
    print(f"  {label:28s} " + " | ".join(out))


print("\ntaker screen at next real fill after fees, top/bottom 10% of signal (threshold from Jan-Apr):")
for f in ["okx_sv60", "okx_sv300", "okx_imb300", "bin_imb30", "own_ret60", "own_ret300"]:
    trade(d[f], f)
# residual signal: flow orthogonal to own return
for f in ["okx_sv60", "okx_sv300", "okx_imb300"]:
    b, _ = ols(d[["own_ret60", "own_ret300"]].values, d[f].values)
    r = d[f] - np.column_stack([np.ones(len(d)), d[["own_ret60", "own_ret300"]].values]) @ b
    trade(r, f + " _|_ own ret")
trade(d.p_model - d.mid, "model - mid (spot staleness)")
