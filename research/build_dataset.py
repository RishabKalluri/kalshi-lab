"""Build a per-(market, horizon) research table from backfilled Kalshi trades + Binance 1s spot.

    uv run python research/build_dataset.py KXBTC15M   ->  research/data/KXBTC15M.parquet

Columns
  ticker, close (UTC), h (seconds before close), y (1 = YES)
  bid, ask, mid       trade-implied quotes (last taker sell / taker buy price), in probability units
  S, K, basis, D      spot (Binance), strike, basis (K - our pre-open 60s avg), D = S + basis - K
  rv_5m, rv_15m, rv_60m, rv_4h   trailing realized vol, $/sqrt(s), from 1s returns
  rv_fut              realized vol from t to close (ex post; for research only, never a feature)
  move_fut            S(close) - S(t)
  iv                  market-implied vol: D / (Phi^-1(mid) * sqrt(h - 40)), when well defined
  next_ask, next_bid  next taker-buy / taker-sell price within 10s after t (realistic taker fill)
  age_ask, age_bid    seconds since the last trade on each side
"""

import json
import math
import os
import sys
from pathlib import Path

import numpy as np
import pandas as pd

from kalshi_lab.data.normalize import iso_ns
from kalshi_lab.recorder.sink import EXT, read_lines

series = sys.argv[1] if len(sys.argv) > 1 else "KXBTC15M"
# By default the dataset stops at the lockbox start, so research can't see lockbox data. --include-lockbox
# (for refitting models used in paper/live trading, by the user/maintainer) writes <SERIES>_all.parquet.
INCLUDE_LOCKBOX = "--include-lockbox" in sys.argv
from kalshi_lab.validate import LOCKBOX_START  # noqa: E402
BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
from kalshi_lab.recorder.config import settlement, spot_map  # noqa: E402
SPOT = spot_map([series], backfill=True)[series][0]
# Crypto settles on a 60s average (strike = 60s average before open); gold on a single 1-minute close.
POINT = settlement(series) == "point"
HORIZONS = [int(x) for x in os.environ.get("HORIZONS", "840,720,600,480,360,300,240,180,120,90,60").split(",")]
TAG = os.environ.get("TAG", "") + ("_all" if INCLUDE_LOCKBOX else "")
OUT = Path(__file__).parent / "data"
OUT.mkdir(exist_ok=True)

# --- spot: dense 1s array + cumulative squared returns for O(1) window RV
secs, px = [], []
CUT = LOCKBOX_START.strftime("%Y-%m-%d")  # without --include-lockbox, never open lockbox-dated files (the research
for f in sorted((BF / "spot" / SPOT).glob(f"*{EXT}")):  # server doesn't even let agents read them)
    if not INCLUDE_LOCKBOX and f.name[:10] >= CUT:
        continue
    for line in read_lines(f):
        d = json.loads(line)
        secs.append(d["t"] // 10**9)
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


def S(t):
    i = t - T0
    return spot[i] if 0 <= i < len(spot) else math.nan


def rv(a, b):  # realized vol over seconds (a, b]
    ia, ib = a - T0, b - T0
    if ia < 0 or ib >= len(cum) or ib <= ia:
        return math.nan
    return math.sqrt((cum[ib] - cum[ia]) / (ib - ia))


def ndtri(p):
    from statistics import NormalDist
    return NormalDist().inv_cdf(p)


rows = []
for day in sorted(p for p in (BF / "kalshi" / series).iterdir() if p.is_dir()):
    if not INCLUDE_LOCKBOX and day.name >= CUT:  # folders are by close day; these markets all close >= the lockbox
        continue
    for f in sorted(day.glob(f"*{EXT}")):
        lines = [json.loads(l) for l in read_lines(f)]
        if lines[-1]["m"].get("event") != "settled":
            continue
        m = lines[-1]["m"]["market"]
        K = m.get("floor_strike")
        if K is None or not m.get("result"):
            continue
        open_s, close_s = iso_ns(m["open_time"]) // 10**9, iso_ns(m["close_time"]) // 10**9
        if not INCLUDE_LOCKBOX and close_s >= LOCKBOX_START.timestamp():
            continue
        if math.isnan(S(open_s - 4 * 3600)) or math.isnan(S(close_s)):
            continue
        basis = K - (S(open_s) if POINT else float(np.mean(spot[open_s - 60 - T0: open_s - T0])))
        trades = [(d["t"] // 10**9, float(d["m"]["msg"]["yes_price_dollars"]), d["m"]["msg"]["taker_side"])
                  for d in lines if d["m"].get("type") == "trade"]
        j, buy, sell, n_tr = 0, None, None, 0
        buy_t = sell_t = None
        for h in HORIZONS:
            t = close_s - h
            while j < len(trades) and trades[j][0] <= t:
                _, p, side = trades[j]
                if side == "yes":
                    buy, buy_t = p, trades[j][0]
                else:
                    sell, sell_t = p, trades[j][0]
                j += 1
            if buy is None or sell is None or buy < sell:
                continue
            mid = (buy + sell) / 2
            # What a taker would actually pay: the next same-side trade within 10s (None if none).
            nxt_buy = next((p for tt, p, sd in trades[j:] if sd == "yes" and tt <= t + 10), None)
            nxt_sell = next((p for tt, p, sd in trades[j:] if sd == "no" and tt <= t + 10), None)
            D = S(t) + basis - K
            iv = math.nan
            if 0.03 < mid < 0.97 and abs(mid - 0.5) > 0.07:
                z = ndtri(mid)
                if z * D > 0:
                    iv = D / (z * math.sqrt(h if POINT else h - 40))
            rows.append(dict(
                ticker=m["ticker"], close=pd.Timestamp(close_s, unit="s", tz="UTC"), h=h, y=int(m["result"] == "yes"),
                bid=sell, ask=buy, mid=mid, S=S(t), K=K, basis=basis, D=D,
                rv_5m=rv(t - 300, t), rv_15m=rv(t - 900, t), rv_60m=rv(t - 3600, t), rv_4h=rv(t - 14400, t),
                rv_fut=rv(t, close_s), move_fut=S(close_s) - S(t), iv=iv, n_trades=j,
                next_ask=nxt_buy, next_bid=nxt_sell, age_ask=t - buy_t, age_bid=t - sell_t,
            ))
df = pd.DataFrame(rows)
df.to_parquet(OUT / f"{series}{TAG}.parquet")
print(f"{series}: {df.ticker.nunique()} markets, {len(df)} rows -> {OUT / f'{series}{TAG}.parquet'}")
print(df.describe().T[["mean", "50%", "min", "max"]].round(3).to_string())
