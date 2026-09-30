"""Implied vs realized vol for Kalshi 15m markets. Train on the first half of dates, test on the second."""

import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

series = sys.argv[1] if len(sys.argv) > 1 else "KXBTC15M"
df = pd.read_parquet(Path(__file__).parent / "data" / f"{series}.parquet")
df["hour"] = df.close.dt.hour
df["dow"] = df.close.dt.dayofweek
split = df.close.quantile(0.5)
train, test = df[df.close < split], df[df.close >= split]
print(f"{series}: train {train.ticker.nunique()} markets (<{split:%m-%d %H:%M}), test {test.ticker.nunique()}\n")

# 1) Level: implied vs trailing vs future realized
v = df.dropna(subset=["iv"])
print("medians ($/sqrt s):", {c: round(v[c].median(), 2) for c in ["iv", "rv_5m", "rv_15m", "rv_60m", "rv_4h", "rv_fut"]})

# 2) Forecasting future realized vol (log RMSE), fit on train
def fit_forecast(tr):
    """log rv_fut ~ a + b1 log rv_15m + b2 log rv_60m + b3 log rv_4h + hour-of-day effects."""
    X = lambda d: np.column_stack([np.ones(len(d)), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
                                   *[(d.hour == hh).astype(float) for hh in range(1, 24)], np.log(d.h)])
    ok = tr.rv_fut > 0.05
    beta, *_ = np.linalg.lstsq(X(tr[ok]), np.log(tr.rv_fut[ok]), rcond=None)
    return lambda d: np.exp(X(d) @ beta)

fc = fit_forecast(train)
df["rv_fc"] = fc(df)
for name, d in (("train", df[df.close < split]), ("test", df[df.close >= split])):
    d = d[(d.rv_fut > 0.05)].dropna(subset=["iv"])
    e = lambda col: np.sqrt(np.mean((np.log(d[col]) - np.log(d.rv_fut)) ** 2))
    k = np.exp(np.median(np.log(d.iv / d.rv_fut)))
    print(f"  {name}: log-RMSE vs future RV  iv/{k:.2f}: {np.sqrt(np.mean((np.log(d.iv / k) - np.log(d.rv_fut))**2)):.3f}"
          f"   rv_15m: {e('rv_15m'):.3f}   rv_60m: {e('rv_60m'):.3f}   forecast: {e('rv_fc'):.3f}")

# 3) Does our vol forecast add information to the market price? Probability models, fit on train.
def features(d, kvol):
    tau = np.sqrt(d.h - 40)
    z_mkt = norm.ppf(d.mid.clip(0.005, 0.995))
    z_fc = d.D / (kvol * d.rv_fc * tau)
    return z_mkt, z_fc

def brier(p, y):
    return np.mean((p - y) ** 2)

tr = df[df.close < split]
# scale factor for forecast vol so the pure-forecast model is calibrated on train (fat tails)
best = min(np.arange(0.8, 2.5, 0.05), key=lambda k: brier(norm.cdf(features(tr, k)[1]), tr.y))
print(f"\n  vol multiplier for forecast model (fit on train): {best:.2f}")
from sklearn.linear_model import LogisticRegression  # noqa: E402

def design(d):
    zm, zf = features(d, best)
    return np.column_stack([zm, zf.clip(-6, 6)])

for hset in ([840, 720, 600], [480, 360, 300], [240, 180, 120], [90, 60]):
    a, b = tr[tr.h.isin(hset)], df[(df.close >= split) & df.h.isin(hset)]
    lr = LogisticRegression(C=10).fit(design(a), a.y)
    lr_m = LogisticRegression(C=10).fit(design(a)[:, :1], a.y)
    pb, pm = lr.predict_proba(design(b))[:, 1], lr_m.predict_proba(design(b)[:, :1])[:, 1]
    pf = norm.cdf(features(b, best)[1])
    print(f"  h={hset}: test Brier  market {brier(b.mid, b.y):.4f}  market-recal {brier(pm, b.y):.4f}"
          f"  forecast-only {brier(pf, b.y):.4f}  market+forecast {brier(pb, b.y):.4f}"
          f"   coefs(z_mkt, z_fc)={lr.coef_[0].round(2)}")

# 4) Implied/forecast ratio by hour: does the market ignore vol seasonality?
v = df.dropna(subset=["iv"]).copy()
v["ratio"] = v.iv / v.rv_fc
g = v.groupby("hour").agg(ratio=("ratio", "median"), iv=("iv", "median"), rv_fut=("rv_fut", "median"), n=("iv", "size"))
print("\n  by UTC hour: median iv, future rv, iv/forecast")
print(g.round(2).T.to_string())
