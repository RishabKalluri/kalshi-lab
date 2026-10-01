"""H2 follow-up: mean reversion across windows by the size of the previous window's move. Dev data only.

    uv run python strategies/eth-overreact/research/prev_move.py [SERIES]

prev_z = previous window's (settlement avg - strike) / (rv_60m * sqrt(900)) from Binance + basis (A_n - A_{n-1}).
Shows P(y), mid, and YES/NO PnL at next real fills (after fee) at early checkpoints, by prev_z bin and half,
plus the same at later checkpoints. Also H3's underdog side.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
d = pd.read_parquet(ROOT / f"research/data/eth-overreact/{series}_panel.parquet")
z = np.load(ROOT / f"research/data/eth-overreact/binance_{series[2:5].lower()}usdt.npz")
T0, spot = int(z["t0"]), z["px"]
fee = lambda p: 0.07 * p * (1 - p)
d["pnl_buy"] = d.y - d.next_ask - fee(d.next_ask)
d["pnl_sell"] = d.next_bid - d.y - fee(d.next_bid)
d["half"] = np.where(pd.to_datetime(d.close, unit="s") < "2026-05-01", "A", "B")
d["mid"] = (d.ask + d.bid) / 2
# A_n: 60 s Binance average before boundary n (the settlement average of window n, and window n+1's strike)
closes = np.sort(d.close.unique())
allb = np.unique(np.concatenate([closes, closes - 900, closes - 1800]))
A = {int(c): spot[c - 60 - T0: c - T0].mean() for c in allb if c - 60 - T0 >= 0 and c - T0 <= len(spot)}
mk = d.groupby("close").agg(rv=("rv_60m", "first")).reset_index()
mk["prev_ret"] = [A.get(c - 900, np.nan) - A.get(c - 1800, np.nan) for c in mk.close]
mk["prev2_ret"] = [A.get(c - 1800, np.nan) - A.get(c - 2700, np.nan) if (c - 2700) in A else np.nan for c in mk.close]
mk["prev_z"] = mk.prev_ret / (mk.rv * 30)
mk["prev2_z"] = mk.prev2_ret / (mk.rv * 30)
d = d.merge(mk[["close", "prev_z", "prev2_z"]], on="close")
m1 = d.groupby("close").first()
print("corr(outcome sign, prev_z):", np.corrcoef(m1.y * 2 - 1, m1.prev_z.fillna(0))[0, 1].round(4))
bins = [-np.inf, -1.5, -0.75, -0.25, 0.25, 0.75, 1.5, np.inf]
d["pzb"] = pd.cut(d.prev_z, bins)
for lab, sub in [("h 780-870 (first 1.5 min)", d[d.h >= 780]), ("h 480-750", d[(d.h >= 480) & (d.h < 780)]),
                 ("h 180-450", d[(d.h >= 180) & (d.h < 480)])]:
    t = sub.groupby(["pzb", "half"], observed=True).agg(y=("y", "mean"), mid=("mid", "mean"), buy=("pnl_buy", "mean"),
                                                        sell=("pnl_sell", "mean"), n=("pnl_buy", "count")).unstack("half")
    for c in ["y", "mid", "buy", "sell"]:
        t[c] *= 100
    print(f"\n== {lab}: by previous window move (z)")
    print(t.round(2).to_string())
