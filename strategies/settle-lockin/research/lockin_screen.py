"""Screen: does a partial-settlement-average model beat the next real Kalshi fill late in the window?

    uv run python strategies/settle-lockin/research/lockin_screen.py KXETH15M
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

series = sys.argv[1]
df = pd.read_parquet(Path(__file__).resolve().parents[3] / "research/data/settle-lockin" / f"{series}_lockin.parquet")
df = df[df.close < "2026-08-20"]
df = df[(df.K / df.ev - 1).abs() < 0.05]  # a few markets have broken strikes
split = pd.Timestamp("2026-05-01", tz="UTC")
df["half"] = np.where(df.close < split, "A", "B")

# 1. How well does Binance + basis track the CF settlement average?
mk = df.drop_duplicates("ticker")
err = mk.ev - mk.bin_avg
sig = mk.rv_60m * np.sqrt(60)  # one-minute move scale
print(f"CF avg - Binance avg: mean {err.mean():.4f}, sd {err.std():.4f}, sd/(1-min move) {(err / sig).std():.3f}, "
      f"median |err|/sig {(err / sig).abs().median():.3f}")
print(f"  sign agreement of (bin_avg - K) with outcome: {((mk.bin_avg >= mk.K) == (mk.y == 1)).mean():.4f}; "
      f"of (ev - K): {((mk.ev >= mk.K) == (mk.y == 1)).mean():.4f}")

# 2. Probability model. sigma per second from trailing vol; e_sd = basis error scale (fit on half A).
mkA = mk[mk.half == "A"]
zA = (mkA.ev - mkA.bin_avg) / (mkA.rv_60m * np.sqrt(60))
e_k = float((zA.quantile(0.95) - zA.quantile(0.05)) / 3.29)  # robust: tails are fat
print(f"basis-error scale (half A) e_k = {e_k:.3f} x 1-min move")


def model(d, vol_mult=1.0, e_mult=1.0):
    h = d.h.values.astype(float)
    s = np.sqrt(0.5 * d.rv_5m.values ** 2 + 0.5 * d.rv_60m.values ** 2) * vol_mult
    inwin = h < 60
    w = (60 - h) / 60
    mean = np.where(inwin, w * d.a_past.values + (1 - w) * d.S.values, d.S.values)
    var_f = np.where(inwin, s ** 2 * h * (h + 1) * (2 * h + 1) / 6 / 3600,
                     s ** 2 * ((h - 60) + 61 * 121 / 6 / 60))
    var_e = (e_k * e_mult * d.rv_60m.values * np.sqrt(60)) ** 2
    return norm.cdf((mean - d.K.values) / np.sqrt(var_f + var_e))


df["p"] = model(df)
# spot-only naive model (what a trader looking at spot vs strike with sqrt(h) would think)
s = np.sqrt(0.5 * df.rv_5m ** 2 + 0.5 * df.rv_60m ** 2)
df["p_naive"] = norm.cdf((df.S - df.K) / (s * np.sqrt(df.h)))
fee = lambda P: 0.07 * P * (1 - P)


def ll(p, y):
    p = np.clip(p, 1e-4, 1 - 1e-4)
    return -np.mean(y * np.log(p) + (1 - y) * np.log(1 - p))


print("\nlog loss by horizon (rows with both next fills): model / naive / next-fill mid / last-trade mid, n")
for h, g in df.dropna(subset=["next_ask", "next_bid"]).groupby("h"):
    nm = (g.next_ask + g.next_bid) / 2
    lm = (g.last_buy + g.last_sell) / 2
    print(f"  h={h:3d}: {ll(g.p, g.y):.4f} {ll(g.p_naive, g.y):.4f} {ll(nm, g.y):.4f} {ll(lm.fillna(nm), g.y):.4f}  n={len(g)}")

# 3. Trade: buy YES at next_ask when p - ask > thr; buy NO at next_bid when bid - p > thr. PnL per contract.
print("\ntaker at next real fill, after fee (cents/contract): thr, horizon bucket, half -> mean, n, t")
out = []
for thr in [0.02, 0.05, 0.10]:
    for side in ["yes", "no"]:
        if side == "yes":
            g = df.dropna(subset=["next_ask"])
            g = g[g.p - g.next_ask > thr + fee(g.next_ask)]
            pnl = g.y - g.next_ask - fee(g.next_ask)
        else:
            g = df.dropna(subset=["next_bid"])
            g = g[g.next_bid - g.p > thr + fee(g.next_bid)]
            pnl = (1 - g.y) - (1 - g.next_bid) - fee(g.next_bid)
        out.append(pd.DataFrame(dict(thr=thr, side=side, h=g.h, half=g.half, pnl=pnl * 100, ticker=g.ticker)))
tr = pd.concat(out)
tr["hb"] = pd.cut(tr.h, [0, 9, 20, 35, 59, 90, 150, 300])
for (thr, hb), g in tr.groupby(["thr", "hb"], observed=True):
    parts = []
    for half in ["A", "B"]:
        x = g[g.half == half].pnl
        parts.append(f"{half}: {x.mean():+6.2f} n={len(x):5d} t={x.mean() / (x.std() / np.sqrt(max(len(x), 2))):+5.1f}")
    print(f"  thr {thr:.2f} h {str(hb):10s} " + " | ".join(parts))
