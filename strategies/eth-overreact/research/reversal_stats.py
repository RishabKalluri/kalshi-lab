"""Is the window-to-window reversal real spot behaviour? Monthly stability of the simple fade. Dev data only.

    uv run python strategies/eth-overreact/research/reversal_stats.py

1. Binance-only: corr of consecutive 15-minute boundary-average returns (A_{n+1}-A_n vs A_n-A_{n-1}, A = 60 s average
   before each :00/:15/:30/:45), per coin and month; and with plain point-to-point returns (no averaging).
2. ETH and SOL: the simple rule (first 1.5 min, |prev_z| > thr, price 30-70c, fade at next fill) by month.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from panel import load_spot  # noqa: E402

from kalshi_lab.validate import LOCKBOX_START  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
LB = int(LOCKBOX_START.timestamp())
print("== 1. Binance-only autocorrelation of consecutive 15-minute returns")
for coin in ["btc", "eth", "sol"]:
    T0, s = load_spot(f"binance_{coin}usdt")
    b0 = ((T0 + 3600) // 900 + 1) * 900
    bnd = np.arange(b0, min(LB, T0 + len(s) - 1), 900)
    A = np.array([s[b - 60 - T0: b - T0].mean() for b in bnd])
    P = s[bnd - T0]
    rA, rP = np.diff(A), np.diff(P)
    mon = pd.to_datetime(bnd[1:], unit="s").strftime("%Y-%m")
    df = pd.DataFrame(dict(rA=rA, rP=rP, mon=mon))
    df["rA1"], df["rP1"] = df.rA.shift(1), df.rP.shift(1)
    vol = df.rA.abs().rolling(16, min_periods=8).mean().shift(1)
    df["zA1"] = df.rA1 / vol
    out = df.groupby("mon").apply(lambda g: pd.Series(dict(
        avg=np.corrcoef(g.rA, g.rA1)[0, 1], point=np.corrcoef(g.rP, g.rP1)[0, 1],
        sign=np.corrcoef(np.sign(g.rA), np.sign(g.rA1))[0, 1], n=len(g))), include_groups=False)
    print(f"\n{coin}: all avg {np.corrcoef(df.rA[1:], df.rA1[1:])[0, 1]:.4f}, point {np.corrcoef(df.rP[1:], df.rP1[1:])[0, 1]:.4f}")
    print(out.round(3).T.to_string())
    big = df[df.zA1.abs() > 1.5 * 1.25]
    print("P(next sign opposite | big prev move):", (np.sign(big.rA) != np.sign(big.rA1)).mean().round(4), len(big))

print("\n== 2. simple fade by month (first 1.5 min, price 30-70c, fade at next fill, cents/contract)")
fee = lambda p: 0.07 * p * (1 - p)
for series in ["KXETH15M", "KXSOL15M"]:
    d = pd.read_parquet(ROOT / f"research/data/eth-overreact/{series}_panel.parquet")
    T0, s = load_spot(f"binance_{series[2:5].lower()}usdt")
    closes = np.sort(d.close.unique())
    A = {int(c): s[c - 60 - T0: c - T0].mean() for c in np.unique(np.concatenate([closes - 900, closes - 1800]))}
    mk = d.groupby("close").rv_60m.first().reset_index()
    mk["prev_z"] = [(A.get(c - 900, np.nan) - A.get(c - 1800, np.nan)) / (r * 30) for c, r in zip(mk.close, mk.rv_60m)]
    d = d.merge(mk[["close", "prev_z"]], on="close")
    d["mid"] = (d.ask + d.bid) / 2
    d = d[(d.h >= 780) & d.mid.between(0.3, 0.7) & (d.age_ask <= 120) & (d.age_bid <= 120)]
    d["mon"] = pd.to_datetime(d.close, unit="s").dt.strftime("%Y-%m")
    for thr in (1.0, 1.5):
        e = d[d.prev_z.abs() > thr].copy()
        up = e.prev_z < 0  # previous window fell -> buy YES
        e["pnl"] = np.where(up, e.y - e.next_ask - fee(e.next_ask), e.next_bid - e.y - fee(e.next_bid))
        e = e.dropna(subset=["pnl"])
        g = e.groupby("mon").pnl.agg(["mean", "count"])
        g["mean"] *= 100
        # market-clustered t: average per market first
        pm = e.groupby("ticker").agg(p=("pnl", "mean"), mon=("mon", "first"))
        t = pm.p.mean() / (pm.p.std() / np.sqrt(len(pm)))
        print(f"\n{series} |prev_z|>{thr}: all {100 * e.pnl.mean():.2f}c n={len(e)} markets={len(pm)} t(market)={t:.2f}")
        print(g.round(2).T.to_string())
