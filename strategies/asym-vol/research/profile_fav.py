"""Is the in-window vol decay priced? Dev data only.

    uv run python strategies/asym-vol/research/profile_fav.py SERIES

By h: median log(iv/rv_fut) and log(iv/rv_inwin) where rv_inwin is realized vol so far in the window (from rv_5m/15m
proxies: rv_15m at h<=600 is mostly in-window). Then favourite PnL at the next real fill after fee by h x price band.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1]
d = pd.read_parquet(ROOT / f"research/data/{series}.parquet")
d = d[d.close < "2026-08-20"].copy()
d["half"] = np.where(d.close < "2026-05-01", "A", "B")
fee = lambda p: 0.07 * p * (1 - p)
fav_yes = d.mid > 0.5
d["fp"] = np.where(fav_yes, d.mid, 1 - d.mid)
d["pnl"] = 100 * np.where(fav_yes, d.y - d.next_ask - fee(d.next_ask), d.next_bid - d.y - fee(d.next_bid))
d["band"] = pd.cut(d.fp, [0.5, 0.6, 0.7, 0.8, 0.9, 0.97], labels=["50-60", "60-70", "70-80", "80-90", "90-97"])
m = d[(d.iv > 0) & (d.rv_fut > 0) & d.mid.between(0.1, 0.9)]
print(series)
print("median log(iv/rv_fut), log(iv/rv_15m), log(rv_fut/rv_15m) by h")
print(m.assign(a=np.log(m.iv / m.rv_fut), b=np.log(m.iv / m.rv_15m), c=np.log(m.rv_fut / m.rv_15m))
      .groupby(["h", "half"])[["a", "b", "c"]].median().unstack("half").round(3).to_string())
print("\nfavourite PnL c/contract (n) at next fill after fee, by h x band")
g = d.dropna(subset=["band", "pnl"]).groupby(["h", "band", "half"], observed=True).pnl.agg(["mean", "count"]).unstack("half")
print(g.round(2).to_string())
