"""Quiet-hours screen: taker PnL vs settlement and markouts, split by when the trade happened.

Screening only. Dev data only (files dated before the lockbox start). Output: per series a parquet of per-trade rows
(aggregated later in buckets.py) so the bucket choice can be changed without re-reading the files.

  python screen.py SERIES [SERIES ...] --out DIR
"""
import argparse
import json
import sys
from datetime import datetime, timezone
from multiprocessing import Pool
from pathlib import Path
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import zstandard

ROOT = Path("/srv/kalshi-data/backfill/kalshi")
LOCKBOX = "2026-09-01"
NS = 10**9
TZ = {"NY": "America/New_York", "LAX": "America/Los_Angeles", "MIA": "America/New_York", "CHI": "America/Chicago",
      "AUS": "America/Chicago", "TATL": "America/New_York", "TBOS": "America/New_York", "TDAL": "America/Chicago",
      "THOU": "America/Chicago", "TPHX": "America/Phoenix"}
HORIZONS = (60, 300, 1800, 3600)


def tz_for(series: str) -> str:
    for k, v in TZ.items():
        if series.endswith(k) or series == "KXLOWT" + k:
            return v
    if series == "KXLOWTNYC":
        return TZ["NY"]
    return "America/New_York"


def iso(s):
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * NS)


def load(path):
    dctx = zstandard.ZstdDecompressor()
    t, side, p, c, settled, disc = [], [], [], [], None, None
    for line in dctx.decompress(path.read_bytes(), max_output_size=2**31).splitlines():
        r = json.loads(line)
        m = r["m"]
        if m.get("type") == "trade":
            x = m["msg"]
            t.append(r["t"]); side.append(x["taker_side"] == "yes")
            p.append(float(x["yes_price_dollars"])); c.append(float(x["count_fp"]))
        elif m.get("event") == "settled":
            settled = m["market"]
        elif m.get("event") == "discovered":
            disc = m["market"]
    if not settled or settled.get("result") not in ("yes", "no") or not t:
        return None
    t, side, p, c = np.array(t, dtype=np.int64), np.array(side), np.array(p), np.array(c)
    o = np.argsort(t, kind="stable")
    t, side, p, c = t[o], side[o], p[o], c[o]
    y = settled["result"] == "yes"
    paid = np.where(side, p, 1 - p)
    won = np.where(side, y, not y).astype(float)
    cols = {"t": t, "paid": paid, "edge": (won - paid) * 100, "c": c, "yes": side, "p": p}
    for h in HORIZONS:
        j = np.searchsorted(t, t + h * NS, side="right") - 1
        later = p[j]
        mk = np.where(side, later - p, p - later) * 100
        ok = t[-1] >= t + h * NS
        cols[f"mk{h}"] = np.where(ok, mk, np.nan)
    df = pd.DataFrame(cols)
    meta = disc or settled
    df["event"] = settled["event_ticker"]
    df["market"] = settled["ticker"]
    df["close_ns"] = iso(settled["close_time"])
    df["exp_ns"] = iso(settled.get("expected_expiration_time") or settled["close_time"])
    df["open_ns"] = iso(meta["open_time"])
    return df


def work(args):
    series, f = args
    try:
        return load(f)
    except Exception as e:  # noqa
        print("ERR", f, e, file=sys.stderr)
        return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series", nargs="+")
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)
    for s in a.series:
        files = sorted(f for f in (ROOT / s).glob("*/*.jsonl.zst") if f.parent.name < LOCKBOX)
        with Pool(4) as pool:
            dfs = [d for d in pool.imap_unordered(work, [(s, f) for f in files], chunksize=8) if d is not None]
        if not dfs:
            continue
        df = pd.concat(dfs, ignore_index=True)
        df.to_parquet(a.out / f"{s}.parquet")
        print(s, len(files), "files", len(df), "trades", df.event.nunique(), "events", flush=True)


if __name__ == "__main__":
    main()
