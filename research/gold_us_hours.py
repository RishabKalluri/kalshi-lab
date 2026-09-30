"""Robustness of the US-hours gold taker signal: thresholds, horizons, bootstrap by market."""
import runpy
import sys

import numpy as np
import pandas as pd

g = runpy.run_path("research/gold_robust.py", run_name="lib")  # reuses its dataframe + fitted model
df, train, test, X, fee, H = g["df"], g["train"], g["test"], g["X"], g["fee"], g["H"]
from sklearn.linear_model import LogisticRegression  # noqa: E402

df["et_hour"] = pd.to_datetime(df.close, unit="s", utc=True).dt.tz_convert("America/New_York").dt.hour
us = df.et_hour.between(8, 16)
models = {h: LogisticRegression(C=10).fit(X(train[train.h == h]), train[train.h == h].y) for h in H}
def signals(d, thr):
    out = []
    for h in H:
        s = d[d.h == h]
        if s.empty:
            continue
        p = models[h].predict_proba(X(s))[:, 1]
        b = s[(p - s.ask > thr) & s.next_ask.notna()]
        a = s[(s.bid - p > thr) & s.next_bid.notna()]
        out.append(pd.DataFrame({"ticker": b.ticker, "h": h, "pnl": b.y - b.next_ask - fee(b.next_ask)}))
        out.append(pd.DataFrame({"ticker": a.ticker, "h": h, "pnl": a.next_bid - a.y - fee(1 - a.next_bid)}))
    return pd.concat(out)
print("\nUS hours (8-17 ET), next-trade fills, both halves pooled:")
for thr in (0.02, 0.03, 0.05, 0.08):
    s = signals(df[us], thr)
    per = s.groupby("ticker").pnl.agg(["sum", "size"])
    boot = [(lambda x: x["sum"].sum() / x["size"].sum())(per.sample(frac=1, replace=True)) for _ in range(3000)]
    lo, hi = np.percentile(boot, [2.5, 97.5])
    tr_ = signals(df[us & (df.close < g["split"])], thr).pnl.mean()
    te_ = signals(df[us & (df.close >= g["split"])], thr).pnl.mean()
    print(f"  thr {thr:.2f}: {s.pnl.mean()*100:+5.2f}c  n={len(s):>4}  markets={s.ticker.nunique():>3}  "
          f"95% CI [{lo*100:+.2f}, {hi*100:+.2f}]   train {tr_*100:+.2f} / test {te_*100:+.2f}")
s = signals(df[us], 0.03)
print("\nby horizon (thr 0.03):", s.groupby("h").pnl.agg(lambda x: f"{x.mean()*100:+.1f}c/{len(x)}").to_dict())
