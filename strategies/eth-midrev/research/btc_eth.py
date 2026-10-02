"""H3 + H4 spot screens (Binance 1 s, dev data only).

    uv run python strategies/eth-midrev/research/btc_eth.py

H3: regress ETH log return [t, t+F] on ETH and BTC log returns [t-L, t], sampled every 30 s; report the BTC coefficient's
    t-stat and the partial correlation, halves A (< May) / B (May - Aug 19).
H4: same but with BTC's return over [t-L, t] and the ETH residual e = r_eth - beta*r_btc (beta from a rolling 1-day
    regression of 1-min returns, shifted); does e predict the future ETH move with a negative sign? Sampled every 60 s.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eth-overreact/research"))
from panel import load_spot  # noqa: E402

from kalshi_lab.validate import LOCKBOX_START  # noqa: E402

LB = int(LOCKBOX_START.timestamp())
MAY = int(pd.Timestamp("2026-05-01", tz="UTC").timestamp())
Te, se = load_spot("binance_ethusdt")
Tb, sb = load_spot("binance_btcusdt")
T0 = max(Te, Tb) + 86400
le = lambda t: np.log(se[t - Te])
lb = lambda t: np.log(sb[t - Tb])


def ols(X, y):
    X = np.column_stack([np.ones(len(y)), X])
    b, *_ = np.linalg.lstsq(X, y, rcond=None)
    r = y - X @ b
    cov = np.linalg.inv(X.T @ X) * (r @ r) / (len(y) - X.shape[1])
    return b[1:], b[1:] / np.sqrt(np.diag(cov))[1:]


print("== H3: BTC lead (coef on BTC past, t-stat), controlling for ETH past")
for L, F in ((10, 10), (30, 30), (60, 60), (120, 120), (30, 300)):
    t = np.arange(T0, LB - 900, 30)
    for half, m in (("A", t < MAY), ("B", t >= MAY)):
        tt = t[m]
        ye = le(tt + F) - le(tt)
        b, ts = ols(np.column_stack([le(tt) - le(tt - L), lb(tt) - lb(tt - L)]), ye)
        print(f"L={L:4d} F={F:4d} {half}: eth_past {b[0]:+.4f} (t {ts[0]:+.1f})  btc_past {b[1]:+.4f} (t {ts[1]:+.1f})")

print("\n== H4: idiosyncratic ETH move vs common move, predicting ETH's next F seconds")
t1 = np.arange(T0 - 86400, LB, 60)
re1, rb1 = np.diff(le(t1)), np.diff(lb(t1))
cov = pd.Series(re1 * rb1).rolling(1440).mean() - pd.Series(re1).rolling(1440).mean() * pd.Series(rb1).rolling(1440).mean()
var = pd.Series(rb1).rolling(1440).var()
beta_1m = (cov / var).shift(1).to_numpy()
beta_at = lambda t: beta_1m[np.clip((t - t1[0]) // 60 - 1, 0, len(beta_1m) - 1)]
for L, F in ((300, 300), (600, 300), (900, 300), (900, 900), (300, 600)):
    t = np.arange(T0, LB - 1800, 60)
    for half, m in (("A", t < MAY), ("B", t >= MAY)):
        tt = t[m]
        beta = beta_at(tt)
        rE, rB = le(tt) - le(tt - L), lb(tt) - lb(tt - L)
        e = rE - beta * rB
        ye = le(tt + F) - le(tt)
        ok = ~np.isnan(beta)
        b1, t1s = ols(rE[ok, None], ye[ok])
        b2, t2s = ols(np.column_stack([e[ok], beta[ok] * rB[ok]]), ye[ok])
        sd = np.nanstd(e)
        print(f"L={L} F={F} {half}: raw eth {b1[0]:+.4f} (t {t1s[0]:+.1f}) | idio {b2[0]:+.4f} (t {t2s[0]:+.1f}) "
              f"common {b2[1]:+.4f} (t {t2s[1]:+.1f}) | beta med {np.nanmedian(beta):.2f}, sd idio/raw {sd / np.std(rE):.2f}")
