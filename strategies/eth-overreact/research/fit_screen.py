"""H4: fit fair = logistic(logit(mid) + b*clip(z, -3, 3)) on Jan-Apr, trade May-Aug at next fills. Dev data only.

    uv run python strategies/eth-overreact/research/fit_screen.py [SERIES]

z = (K_this - K_prev) / (rv_60m * 30): the previous window's move from the strikes (CF settlement averages).
Rows: first 1.5 minutes (h 780-870), mid 25-75c. One trade per market (first checkpoint that triggers).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import expit, logit

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
d = pd.read_parquet(ROOT / f"research/data/eth-overreact/{series}_panel.parquet")
K = d.groupby("close").K.first()
d["K_prev"] = (d.close - 900).map(K)
d["z"] = ((d.K - d.K_prev) / (d.rv_60m * 30)).clip(-3, 3)
d["mid"] = (d.ask + d.bid) / 2
d = d[(d.h >= 780) & d.mid.between(0.25, 0.75) & (d.age_ask <= 120) & (d.age_bid <= 120) & d.z.notna()]
d = d[np.abs(d.K / d.K_prev - 1) < 0.02]
d["half"] = np.where(pd.to_datetime(d.close, unit="s") < "2026-05-01", "A", "B")
d["mon"] = pd.to_datetime(d.close, unit="s").dt.strftime("%Y-%m")
fee = lambda p: 0.07 * p * (1 - p)


def nll(b, x):
    p = np.clip(expit(logit(x.mid) + b * x.z), 1e-6, 1 - 1e-6)
    return -np.mean(x.y * np.log(p) + (1 - x.y) * np.log(1 - p))


tr, te = d[d.half == "A"], d[d.half == "B"]
b = minimize_scalar(lambda b: nll(b, tr), bounds=(-2, 2), method="bounded").x
bB = minimize_scalar(lambda b: nll(b, te), bounds=(-2, 2), method="bounded").x
print(f"{series}: b fit Jan-Apr {b:.4f} (May-Aug alone {bB:.4f}); test log loss mid {nll(0, te):.5f} model {nll(b, te):.5f}")
for margin in (0.0, 0.01, 0.02, 0.03):
    x = te.copy()
    x["fair"] = expit(logit(x.mid) + b * x.z)
    eb = x.fair - x.next_ask - fee(x.next_ask)
    es = x.next_bid - x.fair - fee(x.next_bid)
    x["side"] = np.where(eb > margin, 1, np.where(es > margin, -1, 0))
    x = x[x.side != 0].sort_values(["ticker", "h"], ascending=[True, False]).groupby("ticker").head(1)
    x["pnl"] = np.where(x.side == 1, x.y - x.next_ask - fee(x.next_ask), x.next_bid - x.y - fee(x.next_bid))
    m = x.groupby("mon").pnl.mean() * 100
    se = x.pnl.std() / np.sqrt(len(x))
    print(f"margin {margin:.2f}: {100 * x.pnl.mean():+.2f}c ± {196 * se:.2f} (95%), n={len(x)} markets; by month "
          + " ".join(f"{k[5:]}:{v:+.1f}" for k, v in m.items()))
