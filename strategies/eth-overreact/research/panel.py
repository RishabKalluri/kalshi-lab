"""Per-market checkpoint panel for KXETH15M (development data only, close < LOCKBOX_START).

    uv run python strategies/eth-overreact/research/panel.py [SERIES]

Inputs: the trades dump from settle-lockin (every dev trade with aggressor side), the research dataset (strike K
and basis per ticker), Binance 1 s spot (cached as .npy). One row per (market, h) for h = 870, 840, ..., 30.
Columns: last taker-buy / taker-sell price and age at t, and at t-30/60/120; spot at t and lags; rv_15m, rv_60m;
next taker-buy / taker-sell price in (t, t+10] (a realistic taker fill), y.
"""
import json
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from kalshi_lab.recorder.sink import EXT, read_lines
from kalshi_lab.validate import LOCKBOX_START

ROOT = Path(__file__).resolve().parents[3]
OUT = ROOT / "research/data/eth-overreact"
OUT.mkdir(parents=True, exist_ok=True)
BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
LB = int(LOCKBOX_START.timestamp())


def load_spot(stream):
    cache = OUT / f"{stream}.npz"
    if cache.exists():
        z = np.load(cache)
        return int(z["t0"]), z["px"]
    secs, px = [], []
    for f in sorted((BF / "spot" / stream).glob(f"*{EXT}")):
        if f.name[:10] >= LOCKBOX_START.strftime("%Y-%m-%d"):
            continue
        for line in read_lines(f):
            d = json.loads(line)
            secs.append(d["t"] // 10**9)
            px.append(d["m"]["price"])
    secs, px = np.array(secs), np.array(px, dtype=float)
    t0 = int(secs[0])
    s = np.full(int(secs[-1]) - t0 + 1, np.nan)
    s[secs - t0] = px
    idx = np.where(~np.isnan(s), np.arange(len(s)), 0)
    np.maximum.accumulate(idx, out=idx)
    s = s[idx]
    np.savez(cache, t0=t0, px=s)
    return t0, s


if __name__ == "__main__":
    series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
    coin = {"KXETH15M": "eth", "KXBTC15M": "btc", "KXSOL15M": "sol"}[series]
    T0, spot = load_spot(f"binance_{coin}usdt")
    r2 = np.concatenate([[0.0], np.diff(spot) ** 2])
    cum = np.cumsum(r2)
    ds = pd.read_parquet(ROOT / f"research/data/{series}.parquet", columns=["ticker", "K", "basis"])
    kb = ds.groupby("ticker").first()
    tr = pd.read_parquet(ROOT / f"research/data/settle-lockin/{series}_trades.parquet")
    tr = tr[tr.close < LB].sort_values(["ticker", "t"], kind="stable")
    H = np.arange(870, 0, -30)
    LAGS = [30, 60, 120]
    rows = []
    for tk, g in tr.groupby("ticker", sort=False):
        if tk not in kb.index:
            continue
        K, basis = kb.loc[tk, "K"], kb.loc[tk, "basis"]
        close = int(g.close.iloc[0])
        y = int(g.y.iloc[0])
        t = g.t.to_numpy()
        p = g.price.to_numpy()
        b = g.buy.to_numpy()
        tb, pb = t[b], p[b]
        ts, ps = t[~b], p[~b]

        def last(tt, pp, at):
            i = np.searchsorted(tt, at, side="right") - 1
            ok = i >= 0
            return np.where(ok, pp[np.maximum(i, 0)], np.nan), np.where(ok, at - tt[np.maximum(i, 0)], np.nan)

        def nxt(tt, pp, at, w=10.0):
            i = np.searchsorted(tt, at, side="right")
            ok = (i < len(tt)) & (tt[np.minimum(i, len(tt) - 1)] <= at + w)
            return np.where(ok, pp[np.minimum(i, len(tt) - 1)], np.nan)

        at = close - H.astype(float)
        rec = dict(ticker=np.repeat(tk, len(H)), close=np.repeat(close, len(H)), h=H, y=np.repeat(y, len(H)),
                   K=np.repeat(K, len(H)), basis=np.repeat(basis, len(H)))
        rec["ask"], rec["age_ask"] = last(tb, pb, at)
        rec["bid"], rec["age_bid"] = last(ts, ps, at)
        rec["next_ask"], rec["next_bid"] = nxt(tb, pb, at), nxt(ts, ps, at)
        for L in LAGS:
            rec[f"ask_{L}"], _ = last(tb, pb, at - L)
            rec[f"bid_{L}"], _ = last(ts, ps, at - L)
        ia = (at - T0).astype(int)
        okk = (ia - 14400 >= 0) & (ia < len(spot))
        ia = np.clip(ia, 14400, len(spot) - 1)
        rec["S"] = np.where(okk, spot[ia], np.nan)
        for L in LAGS:
            rec[f"S_{L}"] = np.where(okk, spot[ia - L], np.nan)
        rec["rv_15m"] = np.sqrt((cum[ia] - cum[ia - 900]) / 900)
        rec["rv_60m"] = np.sqrt((cum[ia] - cum[ia - 3600]) / 3600)
        rec["n_before"] = np.searchsorted(t, at, side="right")
        rows.append(pd.DataFrame(rec))
    df = pd.concat(rows, ignore_index=True)
    df = df[np.abs(df.K / df.S - 1) < 0.05]
    df.to_parquet(OUT / f"{series}_panel.parquet")
    print(series, len(df), "rows", df.ticker.nunique(), "markets")
