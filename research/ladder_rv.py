"""Relative value between Kalshi's hourly BTC range markets (KXBTC, thin) and the above/below ladder
(KXBTCD, liquid). Both settle on the same 60s BRTI average.

For every range trade, compute the ladder-implied fair value at that moment,
    fair = P(X > lo - 0.01) - P(X > hi),
with each P from the ladder strike's last trade-implied mid (quotes older than MAX_AGE are skipped).
Then ask:
  1. calibration: Brier of range trade prices vs ladder-implied fair, against the outcome
  2. maker view: if we'd been the passive side of each range trade, PnL vs outcome, bucketed by how
     far the taker paid from fair. Positive = takers in the range market are uninformed relative to
     the ladder, i.e. a maker quoting ranges around ladder fair value would earn it (no maker fees).
"""

import bisect
import json
import os
from collections import defaultdict
from pathlib import Path

import numpy as np
import pandas as pd

from kalshi_lab.data.normalize import iso_ns
from kalshi_lab.recorder.sink import EXT, read_lines

BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill" / "kalshi"
MAX_AGE = 60  # seconds


def load(series):
    out = defaultdict(dict)  # event -> ticker -> dict
    for f in sorted((BF / series).glob(f"*/*{EXT}")):
        lines = [json.loads(l) for l in read_lines(f)]
        m = lines[-1]["m"].get("market", {})
        if not m.get("result"):
            continue
        tr = [(d["t"] / 1e9, float(d["m"]["msg"]["yes_price_dollars"]), d["m"]["msg"]["taker_side"],
               float(d["m"]["msg"]["count_fp"])) for d in lines if d["m"].get("type") == "trade"]
        if not tr:
            continue
        ev = m["event_ticker"].split("-", 1)[1]  # e.g. 26SEP2916: same for KXBTC and KXBTCD
        out[ev][m["ticker"]] = dict(lo=m.get("floor_strike"), hi=m.get("cap_strike"), type=m.get("strike_type"),
                                    y=int(m["result"] == "yes"), trades=tr, close=iso_ns(m["close_time"]) / 1e9)
    return out


ladder, ranges = load("KXBTCD"), load("KXBTC")
rows = []
for ev, rmk in ranges.items():
    lad = ladder.get(ev, {})
    # strike -> (times, mids) from trade-implied quotes
    curves = {}
    for tk, m in lad.items():
        if m["type"] != "greater" or m["lo"] is None:
            continue
        t_, mid_, lb, ls = [], [], None, None
        for t, p, side, q in m["trades"]:
            if side == "yes":
                lb = (t, p)
            else:
                ls = (t, p)
            if lb and ls:
                t_.append(t)
                mid_.append(((lb[1] + ls[1]) / 2, min(lb[0], ls[0])))
        curves[round(m["lo"], 2)] = (t_, mid_)

    def F(k, t):
        c = curves.get(round(k, 2))
        if c is None:
            return None
        i = bisect.bisect_right(c[0], t) - 1
        if i < 0:
            return None
        mid, oldest = c[1][i]
        return mid if t - oldest <= MAX_AGE else None

    for tk, m in rmk.items():
        if m["type"] != "between" or m["lo"] is None or m["hi"] is None:
            continue
        for t, p, side, q in m["trades"]:
            a, b = F(m["lo"] - 0.01, t), F(m["hi"], t)
            if a is None or b is None:
                continue
            fair = min(max(a - b, 0.0), 1.0)
            rows.append(dict(ev=ev, ticker=tk, t=t, tau=m["close"] - t, p=p, side=side, q=q, fair=fair, y=m["y"]))

d = pd.DataFrame(rows)
print(f"{len(d)} range trades with a fresh ladder-implied fair ({d.ticker.nunique()} range markets, {d.ev.nunique()} hours)")
w = d.q
print(f"volume-weighted Brier: range trade price {np.average((d.p - d.y) ** 2, weights=w):.4f}   "
      f"ladder-implied fair {np.average((d.fair - d.y) ** 2, weights=w):.4f}")
# maker PnL per contract: taker bought YES at p -> maker sold -> p - y ; taker sold -> y - p
d["maker"] = np.where(d.side == "yes", d.p - d.y, d.y - d.p)
d["rich"] = np.where(d.side == "yes", d.p - d.fair, d.fair - d.p)  # how much the taker overpaid vs fair
d["half"] = np.where(d.t < d.t.median(), "first", "second")
bins = [-1, -0.03, -0.01, 0.01, 0.03, 1]
d["bucket"] = pd.cut(d.rich, bins, labels=["taker got >3c better than fair", "1-3c better", "within 1c",
                                          "paid 1-3c over fair", "paid >3c over fair"])
g = d.groupby(["bucket", "half"], observed=True).apply(
    lambda x: pd.Series({"maker_c": np.average(x.maker, weights=x.q) * 100, "contracts": x.q.sum(), "n": len(x)}),
    include_groups=False).unstack("half")
print("\nmaker PnL (cents/contract, volume-weighted) if we had been the passive side of each range trade:")
print(g.round(2).to_string())
print(f"\ntotal range volume in sample: {d.q.sum():,.0f} contracts over {d.ev.nunique()} hours")
