"""Dump all Kalshi trades (development data) for a series: ticker, close, t, price, side, qty, y.
    uv run python strategies/settle-lockin/research/trades_dump.py KXETH15M"""
import json, os, sys
from pathlib import Path
import pandas as pd
from kalshi_lab.data.normalize import iso_ns
from kalshi_lab.recorder.sink import EXT, read_lines
from kalshi_lab.validate import LOCKBOX_START
series = sys.argv[1]
BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
LB = int(LOCKBOX_START.timestamp())
rows = []
for day in sorted(p for p in (BF / "kalshi" / series).iterdir() if p.is_dir()):
    if day.name >= LOCKBOX_START.strftime('%Y-%m-%d'):
        continue
    for f in sorted(day.glob(f"*{EXT}")):
        lines = [json.loads(l) for l in read_lines(f)]
        if lines[-1]["m"].get("event") != "settled":
            continue
        m = lines[-1]["m"]["market"]
        if not m.get("result") or m.get("floor_strike") is None:
            continue
        close_s = iso_ns(m["close_time"]) // 10**9
        if close_s >= LB:
            continue
        y = int(m["result"] == "yes")
        for d in lines:
            if d["m"].get("type") == "trade":
                x = d["m"]["msg"]
                rows.append((m["ticker"], close_s, d["t"] / 1e9, float(x["yes_price_dollars"]),
                             x["taker_side"] == "yes", float(x.get("count_fp") or 0), y))
df = pd.DataFrame(rows, columns=["ticker", "close", "t", "price", "buy", "qty", "y"])
df.to_parquet(Path(__file__).resolve().parent / "data" / f"{series}_trades.parquet")
print(series, len(df), "trades", df.ticker.nunique(), "markets")
