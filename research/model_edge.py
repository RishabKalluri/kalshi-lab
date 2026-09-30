"""Spot model vs market, fit on the first half of dates, scored on the second.

  gold  : P(yes) = Phi(D / sqrt(k^2 * rv^2 * h + b^2))   (single-print settlement + basis noise)
  crypto: P(yes) = Phi(D / (k * rv * sqrt(h - 40)))       (60s-average settlement)

Reports Brier (market, model, logistic blend of both) and the PnL of a taker rule that buys YES when
blend - ask > thr (sells when bid - blend > thr), at the trade-implied quotes, after fees.

    uv run python research/model_edge.py KXGOLD15M [_open]
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression

series = sys.argv[1] if len(sys.argv) > 1 else "KXGOLD15M"
tag = sys.argv[2] if len(sys.argv) > 2 else ""
point = series == "KXGOLD15M"
df = pd.read_parquet(Path(__file__).parent / "data" / f"{series}{tag}.parquet").dropna(subset=["rv_60m"])
df = df[df.rv_60m > 0]
split = df.close.quantile(0.5)
tr, te = df[df.close < split], df[df.close >= split]


def z_model(d, k, b):
    if point:
        return d.D / np.sqrt(k ** 2 * d.rv_60m ** 2 * d.h + b ** 2)
    return d.D / (k * d.rv_60m * np.sqrt(d.h - 40))


def brier(p, y):
    return float(np.mean((p - y) ** 2))


res = minimize(lambda x: brier(norm.cdf(z_model(tr, abs(x[0]), abs(x[1]))), tr.y), [1.2, 1.0], method="Nelder-Mead")
k, b = abs(res.x[0]), abs(res.x[1])
print(f"{series}{tag}: train {tr.ticker.nunique()} / test {te.ticker.nunique()} markets. fitted vol mult {k:.2f}, basis noise ${b:.2f}\n")
fee = lambda p: 0.07 * p * (1 - p)
X = lambda d: np.column_stack([norm.ppf(d.mid.clip(0.005, 0.995)), z_model(d, k, b).clip(-8, 8)])
print(f"{'h':>5} {'n':>5} {'Brier mkt':>10} {'model':>8} {'blend':>8}  {'coef mkt,model':>15}   taker rule after fees (test)")
for h in sorted(df.h.unique(), reverse=True):
    a, t = tr[tr.h == h], te[te.h == h]
    if len(a) < 100 or len(t) < 100:
        continue
    lr = LogisticRegression(C=10).fit(X(a), a.y)
    pb = lr.predict_proba(X(t))[:, 1]
    pm = norm.cdf(z_model(t, k, b))
    cells = []
    for thr in (0.03, 0.06, 0.10):
        buy, sell = pb - t.ask > thr, t.bid - pb > thr
        pnl = np.concatenate([(t.y - t.ask - fee(t.ask))[buy], (t.bid - t.y - fee(1 - t.bid))[sell]])
        cells.append(f">{thr:.2f}: {pnl.mean() * 100 if len(pnl) else float('nan'):+6.2f}c (n={len(pnl)})")
    label = f"+{900 - h}s" if tag == "_open" else f"T-{h}"
    print(f"{label:>5} {len(t):>5} {brier(t.mid, t.y):>10.4f} {brier(pm, t.y):>8.4f} {brier(pb, t.y):>8.4f}  "
          f"{str(lr.coef_[0].round(2)):>15}   " + "  ".join(cells))
