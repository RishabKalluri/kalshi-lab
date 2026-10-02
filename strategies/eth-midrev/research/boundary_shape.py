"""Where in the 15-minute cycle does the reversal live? Binance 1 s, dev data only.

    uv run python strategies/eth-midrev/research/boundary_shape.py

For points t at offset o (s after :00/:15/:30/:45), short returns r_pre = P(t) - P(t-L) and r_post = P(t+L) - P(t)
(point prices, L = 60/180/300 s). Report corr(r_pre, r_post) and P(flip | |r_pre| > 2 sd), by o, halves A / B.
Also: hourly boundaries (:00) vs quarter-hour (:15/:30/:45).
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
coins = sys.argv[1:] or ["eth", "btc", "sol"]
for coin in coins:
    T0, s = load_spot(f"binance_{coin}usdt")
    ls = np.log(s)
    print(f"\n== {coin}")
    for L in (60, 180, 300):
        rows = []
        for o in range(-300, 330, 30):
            b0 = ((T0 + 7200) // 900 + 1) * 900
            b = np.arange(b0, LB - 1800, 900)
            t = b + o
            rp = ls[t - T0] - ls[t - L - T0]
            rn = ls[t + L - T0] - ls[t - T0]
            sd = pd.Series(rp).abs().rolling(96, min_periods=20).mean().shift(1).to_numpy() * 1.25
            big = np.abs(rp) > 2 * sd
            for half, m in (("A", b < MAY), ("B", b >= MAY)):
                k = m & ~np.isnan(sd)
                rows.append(dict(o=o, half=half, corr=np.corrcoef(rp[k], rn[k])[0, 1],
                                 flip=(np.sign(rn[k & big]) != np.sign(rp[k & big])).mean(), n=(k & big).sum()))
        df = pd.DataFrame(rows).pivot(index="o", columns="half", values=["corr", "flip", "n"])
        print(f"-- L={L}s (o<0: t before the boundary; t=b+o; pre = [t-L,t], post = [t,t+L])")
        print(df.round(3).to_string())
