"""H1 screen: is the 15-minute sign reversal tied to window boundaries or present at every clock offset?
Binance 1 s only, development data (< LOCKBOX_START).

    uv run python strategies/eth-midrev/research/offset_rev.py

For each offset o (seconds after :00/:15/:30/:45), points t = boundary + o. A(t) = 60 s average ending at t.
r_prev = A(t) - A(t-900), r_next = A(t+900) - A(t). z = r_prev / (mean |r| of the previous 16 intervals).
Report P(sign flips | |z| > 1.5*1.25 ~ |z_sd|>1.5) and the sign correlation, halves A (< May) / B (May - Aug 19).
Also the shorter horizon: given a big trailing 15-min move at t, P(the next h seconds go against it), h = 300/450/600.
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
for coin in ["eth", "btc", "sol"]:
    T0, s = load_spot(f"binance_{coin}usdt")
    cs = np.concatenate([[0.0], np.cumsum(s)])
    avg = lambda t: (cs[t - T0] - cs[t - T0 - 60]) / 60  # mean of s[t-60 .. t-1]
    print(f"\n== {coin}")
    rows = []
    for o in range(0, 900, 60):
        b0 = ((T0 + 7200) // 900 + 1) * 900 + o
        t = np.arange(b0, LB - 1800, 900)
        rp = avg(t) - avg(t - 900)
        rn = avg(t + 900) - avg(t)
        vol = pd.Series(np.abs(rp)).rolling(16, min_periods=8).mean().shift(1).to_numpy()
        z = rp / vol
        big = np.abs(z) > 1.875
        for half, m in (("A", t < MAY), ("B", t >= MAY)):
            k = big & m
            rows.append(dict(o=o, half=half, n=k.sum(), p_flip=(np.sign(rn[k]) != np.sign(rp[k])).mean(),
                             sign_corr=np.corrcoef(np.sign(rn[m & ~np.isnan(z)]), np.sign(rp[m & ~np.isnan(z)]))[0, 1]))
    df = pd.DataFrame(rows).pivot(index="o", columns="half", values=["p_flip", "sign_corr", "n"])
    print(df.round(3).to_string())
