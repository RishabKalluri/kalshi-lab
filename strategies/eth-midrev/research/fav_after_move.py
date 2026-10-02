"""H2 screen: buy the favourite after a big in-window move, vs the same price bucket without one. Dev data only.

    uv run python strategies/eth-midrev/research/fav_after_move.py [SERIES]

z_el = (A(t) - A(open)) / (rv_60m * sqrt(elapsed)): the in-window move in units of hourly vol over the elapsed time.
Favourite = side with mid > 0.5; buy at the next real fill (next taker-buy price for YES, 1 - next taker-sell for NO),
after the taker fee. Grid: favourite price bucket x |z_el| bucket x horizon left, halves A (< May) / B (May - Aug 19).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eth-overreact/research"))
from panel import load_spot  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
coin = series[2:5].lower()
MAY = int(pd.Timestamp("2026-05-01", tz="UTC").timestamp())
fee = lambda p: 0.07 * p * (1 - p)
T0, s = load_spot(f"binance_{coin}usdt")
cs = np.concatenate([[0.0], np.cumsum(s)])
avg = lambda t: (cs[t - T0] - cs[t - T0 - 60]) / 60
d = pd.read_parquet(ROOT / f"research/data/eth-overreact/{series}_panel.parquet")
t = (d.close - d.h).astype(int).to_numpy()
op = d.close.to_numpy().astype(int) - 900
d["z_el"] = (avg(t) - avg(op)) / (d.rv_60m * np.sqrt(900 - d.h))
d["mid"] = (d.ask + d.bid) / 2
d["half"] = np.where(d.close < MAY, "A", "B")
d = d[(d.age_ask <= 120) & (d.age_bid <= 120) & (d.h <= 780) & (d.h >= 60)]
yes = d.mid > 0.5
d["fav_px"] = np.where(yes, d.next_ask, 1 - d.next_bid)
d["pnl"] = np.where(yes, d.y - d.next_ask, d.next_bid - d.y) - fee(d.fav_px)
d = d.dropna(subset=["pnl"])
d["agree"] = np.sign(d.z_el) == np.where(d.mid > 0.5, 1, -1)  # favourite is the side the move created
d["pb"] = pd.cut(d.fav_px, [0.5, 0.65, 0.8, 0.95], labels=["50-65", "65-80", "80-95"])
d["zb"] = pd.cut(d.z_el.abs(), [0, 1, 1.5, 2, 3, 99], labels=["<1", "1-1.5", "1.5-2", "2-3", "3+"])
d["hb"] = pd.cut(d.h, [0, 300, 540, 800], labels=["60-300", "300-540", "540-780"])
d = d[d.agree & d.pb.notna()]
for hb, e in d.groupby("hb", observed=True):
    print(f"\n== {series} h {hb}: favourite PnL c/contract (n) by |z_el| x price, halves")
    g = e.groupby(["pb", "zb", "half"], observed=True).pnl.agg(c=lambda x: 100 * x.mean(), n="size").unstack("half")
    print(g.round(2).to_string())
# market-level (first checkpoint per market) for |z_el| > 2, all h
f = d[d.z_el.abs() > 2].sort_values("h", ascending=False).groupby("ticker").head(1)
print("\nfirst trigger |z_el|>2:", f.groupby("half").pnl.agg(c=lambda x: 100 * x.mean(), se=lambda x: 100 * x.std() / np.sqrt(len(x)), n="size").round(2).to_dict("index"))
