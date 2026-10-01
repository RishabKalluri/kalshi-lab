"""H4: fade PnL by the reversal side's price at entry (has the market already priced the reversal?). Dev only."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
d = pd.read_parquet(ROOT / f"research/data/eth-overreact/{series}_panel.parquet")
K = d.groupby("close").K.first()
d["K_prev"] = (d.close - 900).map(K)
d["z"] = (d.K - d.K_prev) / (d.rv_60m * 30)
d["mid"] = (d.ask + d.bid) / 2
d["half"] = np.where(pd.to_datetime(d.close, unit="s") < "2026-05-01", "A", "B")
fee = lambda p: 0.07 * p * (1 - p)
e = d[(d.h >= 780) & d.mid.between(0.3, 0.7) & (d.z.abs() > 1.5) & (d.age_ask <= 120) & (d.age_bid <= 120)]
e = e.sort_values(["ticker", "h"], ascending=[True, False]).groupby("ticker").head(1).copy()
e["px"] = np.where(e.z < 0, e.mid, 1 - e.mid)       # reversal side's mid
e["win"] = np.where(e.z < 0, e.y, 1 - e.y)
e["pnl"] = np.where(e.z < 0, e.y - e.next_ask - fee(e.next_ask), e.next_bid - e.y - fee(e.next_bid))
e["pb"] = pd.cut(e.px, [0.3, 0.45, 0.5, 0.55, 0.6, 0.7])
t = e.groupby(["pb", "half"], observed=True).agg(px=("px", "mean"), win=("win", "mean"), pnl=("pnl", "mean"),
                                                  n=("pnl", "count")).unstack("half")
print(series); print((t * [100] * 6 + [0] * 0 if False else t).round(3).to_string())
