"""Taker PnL (after fee) by price round-ness: do takers hitting round-priced resting orders win? Dev data only.

    uv run python strategies/asym-vol/research/round_price.py SERIES

Per trade: taker YES-buy PnL = y - p - fee; taker YES-sell (NO-buy) = p - y - fee. Grouped by the price's last digit
class (x0, x5, other) and price band, halves A (< May) / B (May - Aug 19). Also the PnL of the *next* taker on the same
side within 10 s at a non-round price, to see whether a round price marks a stale level.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1]
t = pd.read_parquet(ROOT / f"research/data/settle-lockin/{series}_trades.parquet")
t = t[t.close < 1787184000]  # 2026-08-20
t["cents"] = (t.price * 100).round().astype(int)
t["h"] = t.close - t.t
t = t[(t.cents >= 5) & (t.cents <= 95) & (t.h > 30)]
fee = 0.07 * t.price * (1 - t.price)
t["pnl"] = 100 * np.where(t.buy, t.y - t.price, t.price - t.y) - 100 * fee
t["cls"] = np.where(t.cents % 10 == 0, "x0", np.where(t.cents % 5 == 0, "x5", "other"))
t["half"] = np.where(t.close < 1777593600, "A", "B")  # 2026-05-01
# the taker's side price: for a NO-buy (YES sell) the NO price is 100 - cents; round-ness is symmetric for x0/x5
t["band"] = pd.cut(np.minimum(t.cents, 100 - t.cents), [0, 20, 35, 50], labels=["5-20", "21-35", "36-50"])
w = t.qty
g = t.assign(pw=t.pnl * w).groupby(["band", "cls", "buy", "half"], observed=True).agg(
    n=("pnl", "size"), pnl=("pnl", "mean"), qty=("qty", "sum"), pw=("pw", "sum"))
g["pnl_w"] = g.pw / g.qty
print(series, len(t), "trades")
print(g[["n", "pnl", "pnl_w"]].unstack("half").round(2).to_string())
