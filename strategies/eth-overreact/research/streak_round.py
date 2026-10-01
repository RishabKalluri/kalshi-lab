"""H2 (streaks across windows) and H3 (round-number barriers) screens, development data only.

    uv run python strategies/eth-overreact/research/streak_round.py [SERIES]

PnL per contract at the next real fill (in (t, t+10]) after the taker fee, split Jan-Apr (A) / May-Aug (B).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
d = pd.read_parquet(ROOT / f"research/data/eth-overreact/{series}_panel.parquet")
fee = lambda p: 0.07 * p * (1 - p)
d["pnl_buy"] = d.y - d.next_ask - fee(d.next_ask)
d["pnl_sell"] = d.next_bid - d.y - fee(d.next_bid)
d["half"] = np.where(pd.to_datetime(d.close, unit="s") < "2026-05-01", "A", "B")
d["mid"] = (d.ask + d.bid) / 2
ok = (d.age_ask <= 60) & (d.age_bid <= 60) & (d.ask >= d.bid)

# ---------------- H2: streaks
y_by_close = d.groupby("close").y.first()
# signed streak of the previous windows: +k = k UPs in a row ending at the previous window, -k = k DOWNs
def streak(c):
    s, k = None, 0
    for j in range(1, 7):
        v = y_by_close.get(c - 900 * j)
        if v is None:
            return np.nan if k == 0 else k * (1 if s == 1 else -1)
        if s is None:
            s = v
        if v != s:
            break
        k += 1
    return k * (1 if s == 1 else -1)
st = pd.Series({c: streak(c) for c in y_by_close.index})
d["streak"] = d.close.map(st).clip(-4, 4)
print("serial: P(y=1 | prev y)", d.groupby("close").first().reset_index().assign(prev=lambda x: x.close.sub(900).map(y_by_close))
      .groupby("prev").y.mean().round(4).to_dict())
e = d[(d.h >= 480) & (d.h <= 840)]
t = e.groupby(["streak", "half"]).agg(buy=("pnl_buy", "mean"), sell=("pnl_sell", "mean"), n=("pnl_buy", "count"),
                                      y=("y", "mean"), mid=("mid", "mean")).unstack("half")
print("\n== H2: early window (h 480-840), by previous streak (+k = k UPs)")
print((t * [100, 100, 100, 100, 1, 1, 100, 100, 100, 100]).round(2).to_string())

# ---------------- H3: round levels between spot and strike
f = d[ok & (d.h <= 600) & (d.h >= 60) & d.mid.between(0.55, 0.95) | ok & (d.h <= 600) & (d.h >= 60) & d.mid.between(0.05, 0.45)].copy()
f["fav_yes"] = f.mid > 0.5
f["fav_pnl"] = np.where(f.fav_yes, f.pnl_buy, f.pnl_sell)
f["fav_px"] = np.where(f.fav_yes, f.mid, 1 - f.mid)
Sx = f.S + f.basis  # spot on the strike's scale
lo, hi = np.minimum(Sx, f.K), np.maximum(Sx, f.K)
for step in (25, 50, 100):
    lvl = np.ceil(lo / step) * step
    f[f"rb{step}"] = lvl < hi  # a multiple of `step` lies between spot and strike
f["pxb"] = pd.cut(f.fav_px, [0.55, 0.65, 0.75, 0.85, 0.95])
print("\n== H3: favourite PnL (cents) at next fill, h 60-600, by whether a round level lies between spot and strike")
for step in (25, 50, 100):
    t = f.groupby(["pxb", f"rb{step}", "half"], observed=True).fav_pnl.agg(["mean", "count"]).unstack(["half"])
    t["mean"] *= 100
    print(f"\n-- level step ${step}")
    print(t.round(2).to_string())
