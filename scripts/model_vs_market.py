"""Does a spot-based model know something the market doesn't? For every backfilled market and
several horizons before close, compare the model's P(yes) with the market's price by Brier
score, and measure how often the model is right when the two disagree.

    uv run python scripts/model_vs_market.py [KXBTC15M] [days]
"""

import json
import math
import os
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "strategies" / "_archive"))
from models import prob_up  # noqa: E402

from kalshi_lab.data.normalize import iso_ns  # noqa: E402
from kalshi_lab.recorder.sink import EXT, read_lines  # noqa: E402

series = sys.argv[1] if len(sys.argv) > 1 else "KXBTC15M"
days = float(sys.argv[2]) if len(sys.argv) > 2 else 30
BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
SPOT = {"KXBTC15M": "binance_btcusdt", "KXETH15M": "binance_ethusdt"}[series]
HORIZONS = [600, 300, 180, 120, 60, 45, 30, 20, 10, 5]
VOL_LOOKBACK = 900


def load_spot():
    secs, px = [], []
    for f in sorted((BF / "spot" / SPOT).glob(f"*{EXT}")):
        for line in read_lines(f):
            d = json.loads(line)
            secs.append(d["t"] // 10**9)
            px.append(d["m"]["price"])
    secs, px = np.array(secs), np.array(px)
    t0 = secs[0]
    full = np.full(secs[-1] - t0 + 1, np.nan)
    full[secs - t0] = px
    # forward-fill gaps
    idx = np.where(~np.isnan(full), np.arange(len(full)), 0)
    np.maximum.accumulate(idx, out=idx)
    return t0, full[idx]


t0, spot = load_spot()


def S(sec):  # spot at the end of second `sec`
    i = sec - t0
    return spot[i] if 0 <= i < len(spot) else math.nan


since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
rows = []  # (horizon, model_p, market_p, yes, spread)
for day in sorted(p for p in (BF / "kalshi" / series).iterdir() if p.name >= since):
    for f in sorted(day.glob(f"*{EXT}")):
        lines = [json.loads(l) for l in read_lines(f)]
        if lines[-1]["m"].get("event") != "settled":
            continue
        m = lines[-1]["m"]["market"]
        K = m.get("floor_strike")
        if K is None or not m.get("result"):
            continue
        open_s, close_s = iso_ns(m["open_time"]) // 10**9, iso_ns(m["close_time"]) // 10**9
        if math.isnan(S(open_s - VOL_LOOKBACK)) or math.isnan(S(close_s)):
            continue
        yes = m["result"] == "yes"
        # Basis: strike (BRTI 60s avg before open) minus our 60s average before open.
        basis = K - float(np.mean([S(s) for s in range(open_s - 60, open_s)]))
        trades = [(d["t"] // 10**6, round(float(d["m"]["msg"]["yes_price_dollars"]) * 1000),
                   d["m"]["msg"]["taker_side"]) for d in lines if d["m"].get("type") == "trade"]
        j, last_buy, last_sell = 0, None, None
        for h in sorted(HORIZONS, reverse=True):
            t_s = close_s - h
            while j < len(trades) and trades[j][0] <= t_s * 1000:
                _, px, side = trades[j]
                if side == "yes":
                    last_buy = px
                else:
                    last_sell = px
                j += 1
            if last_buy is None or last_sell is None:
                continue
            mkt = (last_buy + last_sell) / 2 / 1000
            r = np.diff(spot[t_s - VOL_LOOKBACK - t0: t_s - t0 + 1])
            sigma = float(np.sqrt(np.mean(r ** 2)))
            wn = max(0, 60 - h)
            wsum = sum(S(s) for s in range(close_s - 60, close_s - 60 + wn)) + basis * wn
            p = prob_up(S(t_s) + basis, K, h, sigma, wsum, wn)
            rows.append((h, p, mkt, yes, (last_buy - last_sell) / 1000))

rows = np.array(rows, dtype=float)
print(f"{series}: {len(set(rows[:, 0]))} horizons, {int((rows[:, 0] == 60).sum())} markets with data at T-60s\n")
print(f"{'horizon':>8} {'n':>5} {'Brier mkt':>10} {'Brier model':>12} {'blend':>7}   when |model-mkt|>0.05:  n  model right  avg gap  "
      f"edge after spread+fee")
for h in HORIZONS:
    r = rows[rows[:, 0] == h]
    if not len(r):
        continue
    p, q, y, spr = r[:, 1], r[:, 2], r[:, 3], r[:, 4]
    bm, bq, bb = np.mean((q - y) ** 2), np.mean((p - y) ** 2), np.mean(((p + q) / 2 - y) ** 2)
    d = np.abs(p - q) > 0.05
    # Hypothetical take in the model's direction at the trade-implied quote, minus a 1.75c-ish fee.
    buy = p > q
    ask, bid = q + spr / 2, q - spr / 2
    pnl = np.where(buy, y - ask, bid - y) - 0.07 * q * (1 - q)
    print(f"{h:>7}s {len(r):>5} {bm:>10.4f} {bq:>12.4f} {bb:>7.4f}   {d.sum():>22} "
          f"{(np.where(buy, y, 1 - y)[d]).mean() if d.any() else float('nan'):>12.2f} "
          f"{np.abs(p - q)[d].mean() if d.any() else float('nan'):>8.3f} {pnl[d].mean() * 100 if d.any() else float('nan'):>9.2f}c")
print("\nBrier: lower is better. 'blend' = average of model and market; if it beats the market, the model adds information.")
