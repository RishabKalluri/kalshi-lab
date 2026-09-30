"""Fill a recorded-data gap with OKX 1s history, written as a recorder spot stream, so recorded-book
backtests can use it (e.g. gold before the live OKX feed was added).

    uv run python scripts/fetch_okx_into_recorded.py XAU-USDT-SWAP 2026-09-29T03:30 2026-09-29T17:25
    -> <data>/raw/spot/okx_xauusdtswap_hist/...   (use with --spot okx_xauusdtswap_hist)
"""

import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

from kalshi_lab.recorder.sink import Sink

inst, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
to_ms = lambda s: int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp() * 1000)
s_ms, e_ms = to_ms(start), to_ms(end)
root = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser()
stream = f"spot/okx_{inst.replace('-', '').lower()}_hist"
rows, after = {}, e_ms
with httpx.Client(timeout=20) as c:
    while after > s_ms:
        r = c.get("https://www.okx.com/api/v5/market/history-candles",
                  params={"instId": inst, "bar": "1s", "after": after, "limit": 100})
        r.raise_for_status()
        data = r.json()["data"]
        if not data:
            break
        for k in data:
            if int(k[0]) >= s_ms:
                rows[int(k[0])] = float(k[4])
        after = int(data[-1][0])
        time.sleep(0.1)
sink = Sink(root)
for ts, p in sorted(rows.items()):
    sink.write(stream, json.dumps({"type": "ticker", "price": p}), (ts + 1000) * 10**6)
sink.close()
print(f"{len(rows)} seconds -> {root / stream}")
