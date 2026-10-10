"""Per-second variance profile across the 15-minute window (Binance 1 s, dev data only).

    uv run python strategies/asym-vol/research/window_profile.py coin

For each window, squared 1 s returns divided by the window's own mean squared return (so every window weighs the
same), averaged by second-of-window, then summarised in 30 s bins, halves A (< May) / B (May - Aug 19), weekday/weekend.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
coin = sys.argv[1]
z = np.load(ROOT / f"research/data/eth-overreact/binance_{coin}usdt.npz")
T0, px = int(z["t0"]), z["px"]
start = ((T0 + 899) // 900) * 900
lb = 1787184000
n = (min(lb, T0 + len(px)) - start) // 900
idx = start - T0 + np.arange(n * 900 + 1)
r2 = np.diff(np.log(px[idx])) ** 2
W = r2.reshape(n, 900)
mw = W.mean(1, keepdims=True)
ok = (mw[:, 0] > 0) & ((W > 0).mean(1) > 0.3)
W, mw = W[ok], mw[ok]
ts = start + np.arange(n)[ok] * 900
R = W / mw
half = np.where(ts < 1777593600, "A", "B")
dow = pd.to_datetime(ts, unit="s").dayofweek
print(coin, len(R), "windows")
bins = np.arange(0, 901, 30)
for lab, m in [("A", half == "A"), ("B", half == "B"), ("weekend", dow >= 5)]:
    prof = R[m].mean(0)
    b = [prof[bins[i]:bins[i + 1]].mean() for i in range(len(bins) - 1)]
    print(lab, " ".join(f"{x:.2f}" for x in b))
# first/last minute detail (10 s)
prof = R.mean(0)
print("first 120s by 10s:", " ".join(f"{prof[i:i+10].mean():.2f}" for i in range(0, 120, 10)))
print("last 120s by 10s: ", " ".join(f"{prof[i:i+10].mean():.2f}" for i in range(780, 900, 10)))
# remaining variance share vs uniform at h
for h in [840, 720, 600, 480, 300, 180, 120, 60]:
    print(f"h={h}: remaining var share {prof[900-h:].sum()/900:.3f} vs uniform {h/900:.3f}")
