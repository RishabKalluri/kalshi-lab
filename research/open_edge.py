"""At the open, is the market slow to price spot vs strike? Compare market Brier with a pure
spot model and with market+model, per horizon, test half only; plus a simple taker rule."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression

series = sys.argv[1] if len(sys.argv) > 1 else "KXBTC15M"
df = pd.read_parquet(Path(__file__).parent / "data" / f"{series}_open.parquet")
split = df.close.quantile(0.5)
df["zf"] = (df.D / (1.7 * df.rv_60m * np.sqrt(df.h - 40))).clip(-6, 6)
df["zm"] = norm.ppf(df.mid.clip(0.005, 0.995))
fee = lambda p: 0.07 * p * (1 - p)
print(f"{'h':>4} {'n':>5} {'mkt mid':>8} {'Brier mkt':>10} {'model':>8} {'mkt+model':>10}  coef_model  "
      f"{'take when |model-mkt|>':>24}")
for h in sorted(df.h.unique(), reverse=True):
    d = df[df.h == h]
    a, b = d[d.close < split], d[d.close >= split]
    lr = LogisticRegression(C=10).fit(a[["zm", "zf"]], a.y)
    pb = lr.predict_proba(b[["zm", "zf"]])[:, 1]
    pf = norm.cdf(b.zf)
    out = []
    for thr in (0.04, 0.08):
        buy = pb - b.ask > thr
        sell = b.bid - pb > thr
        pnl = np.concatenate([(b.y - b.ask - fee(b.ask))[buy], (b.bid - b.y - fee(1 - b.bid))[sell]])
        out.append(f"{thr:.2f}: {pnl.mean()*100 if len(pnl) else float('nan'):+5.2f}c n={len(pnl)}")
    print(f"{900-h:>3}s {len(b):>5} {b.mid.mean():>8.3f} {np.mean((b.mid-b.y)**2):>10.4f} {np.mean((pf-b.y)**2):>8.4f}"
          f" {np.mean((pb-b.y)**2):>10.4f}  {lr.coef_[0].round(2)}  " + "  ".join(out))
print("\nrows are seconds AFTER open; Brier on the test half; model fit on the train half")
