"""Parallel copy of settle-lockin/research/trades_dump.py (same output, same columns, dev data only).
    uv run python strategies/btc-midrev/research/trades_dump_par.py KXBTC15M"""
import json, os, sys
from multiprocessing import Pool
from pathlib import Path
import pandas as pd
from kalshi_lab.data.normalize import iso_ns
from kalshi_lab.recorder.sink import EXT, read_lines
from kalshi_lab.validate import LOCKBOX_START
BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
LB = int(LOCKBOX_START.timestamp())


def day_rows(day):
    rows = []
    for f in sorted(day.glob(f"*{EXT}")):
        lines = [json.loads(l) for l in read_lines(f)]
        if not lines or lines[-1]["m"].get("event") != "settled":
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
    return pd.DataFrame(rows, columns=["ticker", "close", "t", "price", "buy", "qty", "y"]).astype(
        {"ticker": "category", "close": "int64", "t": "float64", "price": "float32", "qty": "float32", "y": "int8"})


if __name__ == "__main__":
    series = sys.argv[1]
    days = sorted(p for p in (BF / "kalshi" / series).iterdir() if p.is_dir() and p.name < LOCKBOX_START.strftime("%Y-%m-%d") or p.is_dir() and p.name == LOCKBOX_START.strftime("%Y-%m-%d"))
    with Pool(6) as pool:
        parts = pool.map(day_rows, days, chunksize=1)
    df = pd.concat([p for p in parts if len(p)], ignore_index=True)
    df["ticker"] = df.ticker.astype(str)
    df.to_parquet(Path(__file__).resolve().parents[3] / "research/data/settle-lockin" / f"{series}_trades.parquet")
    print(series, len(df), "trades", df.ticker.nunique(), "markets")
