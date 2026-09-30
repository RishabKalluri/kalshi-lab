"""Favorite-longshot check: buying the favorite at the trade-implied ask N seconds before close.
Reports PnL per contract after fees, split into first/second half of the date range.

    uv run python scripts/favorites.py [KXBTC15M]
"""

import json
import math
import os
import sys
from collections import defaultdict
from pathlib import Path

from kalshi_lab.data.normalize import iso_ns
from kalshi_lab.recorder.sink import EXT, read_lines

series = sys.argv[1] if len(sys.argv) > 1 else "KXBTC15M"
BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill" / "kalshi" / series
HORIZONS = [900, 600, 300, 180, 120, 90, 60, 30, 15]
BANDS = [(500, 700), (700, 800), (800, 850), (850, 900), (900, 930), (930, 960), (960, 980), (980, 995)]


def fee(p):  # per contract, 10-lot rounding
    return math.ceil(round(0.07 * 10 * p * (1 - p) * 100, 6)) / 100 / 10


days = sorted(p for p in BF.iterdir() if p.is_dir())
half = days[len(days) // 2].name
res = defaultdict(lambda: [0, 0.0, 0, 0.0])  # (h, band) -> [n1, pnl1, n2, pnl2]
for day in days:
    for f in sorted(day.glob(f"*{EXT}")):
        lines = [json.loads(l) for l in read_lines(f)]
        if lines[-1]["m"].get("event") != "settled":
            continue
        m = lines[-1]["m"]["market"]
        yes = m["result"] == "yes"
        close_ms = iso_ns(m["close_time"]) // 10**6
        trades = [(d["t"] // 10**6, round(float(d["m"]["msg"]["yes_price_dollars"]) * 1000), d["m"]["msg"]["taker_side"])
                  for d in lines if d["m"].get("type") == "trade"]
        j, buy, sell = 0, None, None
        for h in HORIZONS:
            cut = close_ms - h * 1000
            while j < len(trades) and trades[j][0] <= cut:
                _, px, side = trades[j]
                if side == "yes":
                    buy = px  # a taker bought YES here: YES ask
                else:
                    sell = px  # a taker sold YES here: YES bid (NO ask = 1000 - bid)
                j += 1
            if buy is None or sell is None:
                continue
            # Favorite side: whichever is priced above 50c; we pay its ask.
            if buy >= 500:
                cost, win = buy / 1000, yes
            else:
                cost, win = (1000 - sell) / 1000, not yes
            for lo, hi in BANDS:
                if lo <= cost * 1000 < hi:
                    k = res[(h, (lo, hi))]
                    pnl = (1.0 if win else 0.0) - cost - fee(cost)
                    if day.name < half:
                        k[0] += 1; k[1] += pnl
                    else:
                        k[2] += 1; k[3] += pnl

print(f"{series}: buy the favorite at the ask. cells = avg PnL per contract after fees, in cents (n)")
print(f"first half: {days[0].name}..{half}   second half: {half}..{days[-1].name}\n")
print(f"{'ask band':>11} " + "".join(f"{f'T-{h}s':>22}" for h in HORIZONS))
for band in BANDS:
    row = f"{band[0]/1000:.2f}-{band[1]/1000:.3f} "
    for h in HORIZONS:
        n1, p1, n2, p2 = res[(h, band)]
        cell = f"{p1/n1*100:+.1f}({n1})|{p2/n2*100:+.1f}({n2})" if n1 and n2 else "-"
        row += f"{cell:>22}"
    print(row)
