"""Screen: does trailing taker-flow imbalance predict the SOL 15m outcome beyond the Kalshi price?

Copied from sol-flow; run here with SOL's own flow (COIN=sol). Writes screen_*.parquet next to itself (not committed).
(OKX perp + Binance spot) as a cross-asset proxy, plus a same-coin check of the flow idea on ETH itself.

    uv run python strategies/sol-flow/research/flow_screen.py [SERIES] [FLOWCOIN]
"""
import json
import math
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from kalshi_lab.data.flow import load_flow
from kalshi_lab.recorder.sink import EXT, read_lines
from kalshi_lab.validate import LOCKBOX_START

SERIES = sys.argv[1] if len(sys.argv) > 1 else "KXSOL15M"
COIN = sys.argv[2] if len(sys.argv) > 2 else "eth"
ROOT = Path(__file__).resolve().parents[3]
BF = Path("~/kalshi-data/backfill").expanduser()
OUT = Path(__file__).parent

df = pd.read_parquet(ROOT / "research/data" / f"{SERIES}.parquet")
df = df[df["close"] < pd.Timestamp(LOCKBOX_START)].copy()
df["t"] = ((df["close"] - pd.Timestamp(0, tz="UTC")).dt.total_seconds().astype("int64") - df["h"]).astype("int64")
start, end = df["close"].min().date().isoformat(), df["close"].max().date() + pd.Timedelta(days=1)


def dense_cum(source):
    f = load_flow(source, start, end.isoformat(), dense=True)
    t0 = int(f["t"].iloc[0])
    return t0, np.concatenate([[0], np.cumsum(f["buy"].values)]), np.concatenate([[0], np.cumsum(f["sell"].values)]), f["px"].values


def spot_series(stream):
    secs, px = [], []
    for f in sorted((BF / "spot" / stream).glob(f"*{EXT}")):
        for line in read_lines(f):
            d = json.loads(line)
            secs.append(d["t"] // 10**9); px.append(d["m"]["price"])
    s = pd.Series(px, index=secs).groupby(level=0).last()
    full = s.reindex(np.arange(s.index[0], s.index[-1] + 1)).ffill()
    return int(full.index[0]), full.values


t = df["t"].values
sources = {"okx": f"okx_{COIN}usdtswap", "bin": f"binance_{COIN}usdt"}
for tag, src in sources.items():
    t0, cb, cs, fpx = dense_cum(src)
    i = np.clip(t - t0 + 1, 0, len(cb) - 1)  # cum index through second t inclusive
    for w in (30, 60, 120, 300):
        j = np.clip(i - w, 0, len(cb) - 1)
        b, s = cb[i] - cb[j], cs[i] - cs[j]
        df[f"{tag}_imb{w}"] = (b - s) / np.maximum(b + s, 1e-9)
        # signed volume relative to trailing 1h average volume per w seconds
        j60 = np.clip(i - 3600, 0, len(cb) - 1)
        vol1h = (cb[i] - cb[j60] + cs[i] - cs[j60]) / 3600 * w
        df[f"{tag}_sv{w}"] = (b - s) / np.maximum(vol1h, 1e-9)
    ii = np.clip(t - t0, 0, len(fpx) - 1)
    for w in (60, 300):
        df[f"{tag}_ret{w}"] = np.log(fpx[ii] / fpx[np.clip(ii - w, 0, len(fpx) - 1)])

# own-coin trailing return (the series' own spot)
own = {"KXSOL15M": "binance_solusdt", "KXETH15M": "binance_ethusdt", "KXBTC15M": "binance_btcusdt"}[SERIES]
s0, spx = spot_series(own)
k = np.clip(t - s0, 0, len(spx) - 1)
for w in (30, 60, 120, 300):
    df[f"own_ret{w}"] = np.log(spx[k] / spx[np.clip(k - w, 0, len(spx) - 1)])

# standardized future move to settlement (in units of trailing vol * sqrt(h))
sig = df["rv_15m"] * np.sqrt(df["h"])
df["z_fut"] = df["move_fut"] / sig
df["resid"] = df["y"] - df["mid"]
df.to_parquet(OUT / f"screen_{SERIES}_{COIN}.parquet")

print(f"{SERIES} with {COIN} flow: {df.ticker.nunique()} markets, {len(df)} rows, {start}..{end}")
feats = [c for c in df.columns if c.startswith(("okx_", "bin_", "own_"))]
print("\ncorrelation with standardized future spot move (z_fut) and with y - mid, per horizon group")
for hs in [(60, 90, 120), (180, 240, 300), (360, 480, 600)]:
    sub = df[df.h.isin(hs) & np.isfinite(df.z_fut)]
    c1 = sub[feats].corrwith(sub["z_fut"]); c2 = sub[feats].corrwith(sub["resid"])
    print(f"\nh in {hs}: n={len(sub)}")
    print(pd.DataFrame({"z_fut": c1, "y-mid": c2}).round(4).to_string())
