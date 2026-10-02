"""H6 screen: fade the previous window's *late* move (last L s before the open) in the first 1.5 minutes. Dev only.

    uv run python strategies/eth-midrev/research/late_move.py [SERIES]

zL = (A(open) - A(open - L)) / (rv_60m * sqrt(L)), A = 60 s Binance average ending at t. z15 as eth-overreact
(L = 900, rv_60m * 30). Rows: h in 870..780, mid 30-70c, quotes fresh. First trigger per market. Halves A / B.
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
op = d.close.to_numpy().astype(int) - 900
for L in (180, 300, 450, 900):
    d[f"z{L}"] = (avg(op) - avg(op - L)) / (d.rv_60m * np.sqrt(L))
d["z_rest"] = (avg(op - 300) - avg(op - 900)) / (d.rv_60m * np.sqrt(600))  # first 10 min of the previous window
d["mid"] = (d.ask + d.bid) / 2
d["half"] = np.where(d.close < MAY, "A", "B")
d["mon"] = pd.to_datetime(d.close, unit="s").dt.strftime("%m")
d = d[(d.h >= 780) & d.mid.between(0.3, 0.7) & (d.age_ask <= 120) & (d.age_bid <= 120)]


def fade(e, col):
    up = e[col] < 0
    return np.where(up, e.y - e.next_ask - fee(e.next_ask), e.next_bid - e.y - fee(e.next_bid))


def report(mask, col, lab):
    e = d[mask].copy()
    e["pnl"] = fade(e, col)
    e = e.dropna(subset=["pnl"]).sort_values("h", ascending=False).groupby("ticker").head(1)
    g = e.groupby("half").pnl.agg(c=lambda x: 100 * x.mean(), se=lambda x: 100 * x.std() / np.sqrt(len(x)), n="size")
    mo = e.groupby("mon").pnl.mean().mul(100).round(1).to_dict()
    print(f"{lab:38s} A {g.loc['A','c']:+.2f} (se {g.loc['A','se']:.2f}, n {int(g.loc['A','n'])})  "
          f"B {g.loc['B','c']:+.2f} (se {g.loc['B','se']:.2f}, n {int(g.loc['B','n'])})  months {mo}")


print(f"== {series}: first trigger per market, fade at next fill, c/contract")
for L in (180, 300, 450, 900):
    for thr in (1.5, 2.0):
        report(d[f"z{L}"].abs() > thr, f"z{L}", f"|z{L}|>{thr}")
print("-- does the late move add anything beyond the full-window move?")
report((d.z300.abs() > 2.0) & (d.z900.abs() <= 1.5), "z300", "|z300|>2 & |z15|<=1.5 (new markets)")
report((d.z300.abs() > 1.5) & (d.z900.abs() <= 1.5), "z300", "|z300|>1.5 & |z15|<=1.5 (new markets)")
report((d.z900.abs() > 1.5) & (d.z300.abs() <= 1.0), "z900", "|z15|>1.5 & |z300|<=1 (early-move only)")
report((d.z900.abs() > 1.5) & (d.z300.abs() > 1.5) & (np.sign(d.z300) == np.sign(d.z900)), "z900", "both big, same sign")
report((d.z_rest.abs() > 1.5), "z_rest", "|first-10-min z|>1.5")

print("-- robustness of 'both big, same sign' (z15 > 1.5 and late move same sign)")
for L in (180, 300, 450):
    for thr in (1.0, 1.5, 2.0):
        report((d.z900.abs() > 1.5) & (d[f"z{L}"].abs() > thr) & (np.sign(d[f"z{L}"]) == np.sign(d.z900)), "z900",
               f"|z15|>1.5 & |z{L}|>{thr} same sign")
report((d.z900.abs() > 1.5) & ((d.z300.abs() <= 1.5) | (np.sign(d.z300) != np.sign(d.z900))), "z900",
       "|z15|>1.5 & NOT late-confirmed")
