"""Build a last-minutes table per market for the settlement lock-in screen (development data only).

    uv run python strategies/settle-lockin/research/lockin_data.py KXETH15M
-> strategies/settle-lockin/research/<SERIES>_lockin.parquet

Per market x horizon tau (seconds before close): last taker-buy / taker-sell price, next taker fills within
FILL_WIN s, Binance spot S + basis, accumulated settlement average so far (A_past), trailing realized vol,
the CF settlement value (expiration_value) and outcome.
"""
import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from kalshi_lab.data.normalize import iso_ns
from kalshi_lab.recorder.config import spot_map
from kalshi_lab.recorder.sink import EXT, read_lines
from kalshi_lab.validate import LOCKBOX_START

series = sys.argv[1]
BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
SPOT = spot_map([series], backfill=True)[series][0]
HORIZONS = [300, 240, 180, 150, 120, 100, 90, 80, 70, 60, 55, 50, 45, 40, 35, 30, 25, 20, 15, 10, 7, 5, 3]
FILL_WIN = 5
OUT = Path(__file__).resolve().parents[3] / "research/data/settle-lockin" / f"{series}_lockin.parquet"
LB = int(LOCKBOX_START.timestamp())

secs, px = [], []
for f in sorted((BF / "spot" / SPOT).glob(f"*{EXT}")):
    for line in read_lines(f):
        d = json.loads(line)
        s = d["t"] // 10**9
        if s >= LB:
            break
        secs.append(s)
        px.append(d["m"]["price"])
secs, px = np.array(secs), np.array(px)
T0 = int(secs[0])
spot = np.full(int(secs[-1]) - T0 + 1, np.nan)
spot[secs - T0] = px
idx = np.where(~np.isnan(spot), np.arange(len(spot)), 0)
np.maximum.accumulate(idx, out=idx)
spot = spot[idx]
r2 = np.concatenate([[0.0], np.diff(spot) ** 2])
cum = np.cumsum(r2)
csp = np.concatenate([[0.0], np.cumsum(spot)])  # csp[i] = sum spot[0:i]


def S(t):
    i = t - T0
    return spot[i] if 0 <= i < len(spot) else math.nan


def avg(a, b):  # mean of spot over seconds [a, b)
    ia, ib = a - T0, b - T0
    if ia < 0 or ib > len(spot) or ib <= ia:
        return math.nan
    return (csp[ib] - csp[ia]) / (ib - ia)


def rv(a, b):
    ia, ib = a - T0, b - T0
    if ia < 0 or ib >= len(cum) or ib <= ia:
        return math.nan
    return math.sqrt((cum[ib] - cum[ia]) / (ib - ia))


rows = []
for day in sorted(p for p in (BF / "kalshi" / series).iterdir() if p.is_dir()):
    for f in sorted(day.glob(f"*{EXT}")):
        lines = [json.loads(l) for l in read_lines(f)]
        if lines[-1]["m"].get("event") != "settled":
            continue
        m = lines[-1]["m"]["market"]
        K = m.get("floor_strike")
        ev = m.get("expiration_value")
        if K is None or not m.get("result") or not ev:
            continue
        open_s, close_s = iso_ns(m["open_time"]) // 10**9, iso_ns(m["close_time"]) // 10**9
        if close_s >= LB or close_s - open_s != 900:
            continue
        if math.isnan(S(open_s - 3600)) or math.isnan(S(close_s)):
            continue
        basis = K - avg(open_s - 60, open_s)
        trades = [(d["t"] / 1e9, float(d["m"]["msg"]["yes_price_dollars"]), d["m"]["msg"]["taker_side"],
                   float(d["m"]["msg"].get("count_fp") or d["m"]["msg"].get("count") or 0))
                  for d in lines if d["m"].get("type") == "trade"]
        trades.sort()
        j, buy, sell, buy_t, sell_t = 0, None, None, None, None
        for h in HORIZONS:
            t = close_s - h
            while j < len(trades) and trades[j][0] <= t:
                _, p, side, _q = trades[j]
                if side == "yes":
                    buy, buy_t = p, trades[j][0]
                else:
                    sell, sell_t = p, trades[j][0]
                j += 1
            nb = next(((p, q) for tt, p, sd, q in trades[j:] if sd == "yes" and tt <= t + FILL_WIN), (None, None))
            ns = next(((p, q) for tt, p, sd, q in trades[j:] if sd == "no" and tt <= t + FILL_WIN), (None, None))
            n_after = sum(1 for tt, *_ in trades[j:] if tt < close_s)
            a_past = avg(close_s - 60, t) + basis if h < 60 else math.nan
            rows.append(dict(
                ticker=m["ticker"], close=pd.Timestamp(close_s, unit="s", tz="UTC"), h=h, y=int(m["result"] == "yes"),
                K=K, ev=float(ev), bin_avg=avg(close_s - 60, close_s) + basis, basis=basis,
                S=S(t) + basis, a_past=a_past, rv_5m=rv(t - 300, t), rv_60m=rv(t - 3600, t), rv_60s=rv(t - 60, t),
                last_buy=buy, last_sell=sell, age_buy=(t - buy_t) if buy_t else None,
                age_sell=(t - sell_t) if sell_t else None,
                next_ask=nb[0], next_ask_q=nb[1], next_bid=ns[0], next_bid_q=ns[1], n_after=n_after,
            ))
df = pd.DataFrame(rows)
df.to_parquet(OUT)
print(series, df.ticker.nunique(), "markets", len(df), "rows ->", OUT)
