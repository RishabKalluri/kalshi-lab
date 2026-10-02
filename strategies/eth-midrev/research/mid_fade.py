"""H1 Kalshi screen: fade a big trailing 15-minute move at mid-window checkpoints, at the next real fill, after fee.
Development data only (panel from eth-overreact: close < LOCKBOX_START).

    uv run python strategies/eth-midrev/research/mid_fade.py [SERIES]

z15 = (A(t) - A(t-900)) / (rv_60m * 30), A = 60 s Binance average ending at t. Fade: z15 > thr -> buy NO at next bid,
z15 < -thr -> buy YES at next ask. One row per (market, h); also first trigger per market. Halves A (< May) / B.
Also splits the trailing move into its in-window part (spot vs strike) and pre-open part.
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
d["z15"] = (avg(t) - avg(t - 900)) / (d.rv_60m * 30)
d["zin"] = (avg(t) - avg(d.close.to_numpy().astype(int) - 900)) / (d.rv_60m * 30)  # in-window part
d["mid"] = (d.ask + d.bid) / 2
d["half"] = np.where(d.close < MAY, "A", "B")
d = d[(d.age_ask <= 120) & (d.age_bid <= 120) & d.mid.between(0.1, 0.9)]
d["hb"] = pd.cut(d.h, [0, 150, 300, 480, 660, 780, 900], labels=["<150", "150-300", "300-480", "480-660", "660-780", "780+"])


def pnl(e):
    up = e.z15 < 0
    return np.where(up, e.y - e.next_ask - fee(e.next_ask), e.next_bid - e.y - fee(e.next_bid))


for thr in (1.0, 1.5, 2.0):
    e = d[d.z15.abs() > thr].copy()
    e["pnl"] = pnl(e)
    e = e.dropna(subset=["pnl"])
    e["fade_px"] = np.where(e.z15 < 0, e.next_ask, 1 - e.next_bid)
    print(f"\n== {series} |z15|>{thr}: cents/contract by horizon left, half (n rows)")
    g = e.groupby(["hb", "half"], observed=True).agg(c=("pnl", lambda x: 100 * x.mean()), n=("pnl", "size"),
                                                       px=("fade_px", "mean"))
    print(g.unstack("half").round(2).to_string())
    # first trigger per market, h <= 780 only (exclude eth-overreact's opening zone)
    f = e[e.h <= 780].sort_values("h", ascending=False).groupby("ticker").head(1)
    gf = f.groupby("half").pnl.agg(["mean", "std", "count"])
    gf["c"] = 100 * gf["mean"]
    gf["se"] = 100 * gf["std"] / np.sqrt(gf["count"])
    print("first trigger, h<=780:", gf[["c", "se", "count"]].round(2).to_dict("index"))
    # in-window vs straddling: share of the move inside the window
    e2 = e[e.h <= 780].copy()
    e2["inside"] = np.where((e2.zin / e2.z15) > 0.7, "mostly in-window", "mostly pre-open")
    print(e2.groupby(["inside", "half"]).pnl.agg(lambda x: round(100 * x.mean(), 2)).unstack().to_string())
