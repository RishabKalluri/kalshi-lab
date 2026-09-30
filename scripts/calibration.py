"""Is the market's price a calibrated probability? From backfilled trades, take the last trade
price N seconds before close, bucket it, and compare with how often YES actually won.

    uv run python scripts/calibration.py KXBTC15M [days]
"""

import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
import os

from kalshi_lab.data.normalize import iso_ns
from kalshi_lab.recorder.sink import EXT, read_lines

series = sys.argv[1] if len(sys.argv) > 1 else "KXBTC15M"
days = float(sys.argv[2]) if len(sys.argv) > 2 else 30
root = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill" / "kalshi" / series
since = (datetime.now(timezone.utc) - timedelta(days=days)).date().isoformat()
HORIZONS = [600, 300, 120, 60, 30, 10]
BUCKETS = [(0, 50), (50, 150), (150, 300), (300, 450), (450, 550), (550, 700), (700, 850), (850, 950), (950, 1001)]

stats = {h: defaultdict(lambda: [0, 0, 0.0]) for h in HORIZONS}  # bucket -> [n, yes, sum price]
n_markets = 0
for day in sorted(p for p in root.iterdir() if p.name >= since):
    for f in day.glob(f"*{EXT}"):
        lines = [json.loads(l) for l in read_lines(f)]
        meta = lines[-1]["m"]
        if meta.get("event") != "settled":
            continue
        m = meta["market"]
        close = iso_ns(m["close_time"])
        yes = m["result"] == "yes"
        trades = [(d["t"], d["m"]["msg"]["yes_price_dollars"]) for d in lines if d["m"].get("type") == "trade"]
        if not trades:
            continue
        n_markets += 1
        i = 0
        for h in sorted(HORIZONS, reverse=True):
            cut = close - h * 10**9
            while i < len(trades) and trades[i][0] <= cut:
                i += 1
            if i == 0:
                continue
            px = round(float(trades[i - 1][1]) * 1000)
            for lo, hi in BUCKETS:
                if lo <= px < hi:
                    s = stats[h][(lo, hi)]
                    s[0] += 1
                    s[1] += yes
                    s[2] += px / 1000
                    break

print(f"{series}: {n_markets} settled markets since {since}\n")
print("  last trade price N seconds before close vs realized YES rate (n in parens)")
hdr = f"{'price bucket':>13} " + " ".join(f"{f'T-{h}s':>17}" for h in HORIZONS)
print(hdr)
for lo, hi in BUCKETS:
    row = f"{f'{lo/1000:.2f}-{min(hi,1000)/1000:.2f}':>13} "
    for h in HORIZONS:
        n, y, sp = stats[h][(lo, hi)]
        row += f"{(f'{sp/n:.2f}->{y/n:.2f} ({n})' if n else '-'):>17} "
    print(row)
print("\n  cell = avg price -> realized YES rate. A persistent gap bigger than fees (~1.75c at 50c)")
print("  is a candidate edge; check it holds out of sample before believing it.")
