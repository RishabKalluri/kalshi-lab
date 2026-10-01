"""Control: does BTC's (efficient) Kalshi market price the previous-window reversal at h=840/720? Dev data only."""
from pathlib import Path
import numpy as np
import pandas as pd
ROOT = Path(__file__).resolve().parents[3]
for series in ["KXBTC15M", "KXETH15M", "KXSOL15M"]:
    d = pd.read_parquet(ROOT / f"research/data/{series}.parquet")
    d = d[d.close < pd.Timestamp("2026-08-20", tz="UTC")]
    d["c"] = d.close.astype("int64") // 10**9 if d.close.dtype != "int64" else d.close
    d["c"] = (d.close - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds().astype(int)
    K = d.groupby("c").K.first()
    d["z"] = (d.K - (d.c - 900).map(K)) / (d.rv_60m * 30)
    d = d[(d.h == 840) & d.mid.between(0.3, 0.7) & (d.z.abs() > 1.5) & (np.abs(d.K / (d.c - 900).map(K) - 1) < 0.02)]
    fee = lambda p: 0.07 * p * (1 - p)
    d["px"] = np.where(d.z < 0, d.mid, 1 - d.mid)
    d["win"] = np.where(d.z < 0, d.y, 1 - d.y)
    d["pnl"] = np.where(d.z < 0, d.y - d.next_ask - fee(d.next_ask), d.next_bid - d.y - fee(d.next_bid))
    d["half"] = np.where(d.close < pd.Timestamp("2026-05-01", tz="UTC"), "A", "B")
    print(series, d.groupby("half").agg(px=("px", "mean"), win=("win", "mean"), pnl=("pnl", "mean"), n=("pnl", "count")).round(3).to_dict("index"))
