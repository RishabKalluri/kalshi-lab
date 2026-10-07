"""Light opening panel for KXBTC15M (dev only): eth-overreact/research/panel.py's quote/fill columns at h = 870/840/810/780
only, built from the first ~2.2 minutes of trades so BTC's 179M-trade dump fits in memory.

    uv run python strategies/btc-midrev/research/open_panel.py KXBTC15M

Columns as panel.py: ask/bid = last taker-buy/-sell price at t (and age), next_ask/next_bid = next taker-buy/-sell
price in (t, t+10] (a realistic taker fill), y. Output research/data/eth-overreact/<SERIES>_panel.parquet.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pyarrow.parquet as pq

from kalshi_lab.validate import LOCKBOX_START

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1]
LB = int(LOCKBOX_START.timestamp())
H = np.array([870, 840, 810, 780])
pf = pq.ParquetFile(ROOT / f"research/data/settle-lockin/{series}_trades.parquet")
parts = []
for b in pf.iter_batches(batch_size=5_000_000, columns=["ticker", "close", "t", "price", "buy", "y"]):
    x = b.to_pandas()
    parts.append(x[(x.t < x.close - 770) & (x.close < LB)])
tr = pd.concat(parts, ignore_index=True).sort_values(["ticker", "t"], kind="stable")
print(len(tr), "opening trades")
rows = []
for tk, g in tr.groupby("ticker", sort=False):
    close, y = int(g.close.iloc[0]), int(g.y.iloc[0])
    t, p, b = g.t.to_numpy(), g.price.to_numpy(), g.buy.to_numpy()
    tb, pb, ts, ps = t[b], p[b], t[~b], p[~b]

    def last(tt, pp, at):
        i = np.searchsorted(tt, at, side="right") - 1
        ok = i >= 0
        return np.where(ok, pp[np.maximum(i, 0)], np.nan), np.where(ok, at - tt[np.maximum(i, 0)], np.nan)

    def nxt(tt, pp, at, w=10.0):
        if len(tt) == 0:
            return np.full(len(at), np.nan)
        i = np.searchsorted(tt, at, side="right")
        ok = (i < len(tt)) & (tt[np.minimum(i, len(tt) - 1)] <= at + w)
        return np.where(ok, pp[np.minimum(i, len(tt) - 1)], np.nan)

    at = close - H.astype(float)
    rec = dict(ticker=np.repeat(tk, len(H)), close=np.repeat(close, len(H)), h=H, y=np.repeat(y, len(H)))
    if len(tb):
        rec["ask"], rec["age_ask"] = last(tb, pb, at)
    else:
        rec["ask"] = rec["age_ask"] = np.full(len(H), np.nan)
    if len(ts):
        rec["bid"], rec["age_bid"] = last(ts, ps, at)
    else:
        rec["bid"] = rec["age_bid"] = np.full(len(H), np.nan)
    rec["next_ask"], rec["next_bid"] = nxt(tb, pb, at), nxt(ts, ps, at)
    rows.append(pd.DataFrame(rec))
df = pd.concat(rows, ignore_index=True)
df.to_parquet(ROOT / f"research/data/eth-overreact/{series}_panel.parquet")
print(series, len(df), "rows", df.ticker.nunique(), "markets")
