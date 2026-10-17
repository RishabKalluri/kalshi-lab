"""One row per weather market x snapshot time: synthetic ask/bid (last taker-buy / taker-sell YES price, as the
engine's backfill book shows them), ages, last price, outcome. Development dates only (close date < 2026-08-20).
Snapshot times are hours relative to local-standard midnight of the target day D (negative = day before)."""
import json, sys, os
from pathlib import Path
from datetime import datetime, timezone, timedelta
from multiprocessing import Pool
import zstandard as zstd
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
from build_daily import LST
ROOT = Path("/srv/kalshi-data/backfill/kalshi")
LOCKBOX = "2026-08-20"
HOURS = [-30, -24, -18, -12, -6, 0, 3, 6, 9]
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}

def parse(path):
    raw = zstd.ZstdDecompressor().stream_reader(open(path, "rb")).read().decode()
    meta, trades, res = None, [], None
    for l in raw.splitlines():
        j = json.loads(l); m = j["m"]
        if m.get("event") == "discovered": meta = m["market"]
        elif m.get("event") == "settled": res = m["market"]
        elif m.get("type") == "trade":
            g = m["msg"]; trades.append((j["t"] / 1e9, float(g["yes_price_dollars"]), float(g["count_fp"]), g["taker_side"] == "yes"))
    return meta, trades, res

def one(args):
    series, path = args
    meta, trades, res = parse(path)
    if meta is None or res is None or not res.get("result"): return []
    ev = meta["event_ticker"].split("-")[1]  # 26MAR09
    day = datetime(2000 + int(ev[:2]), MON[ev[2:5]], int(ev[5:]))
    mid = day.replace(tzinfo=timezone.utc).timestamp() - LST[series] * 3600  # LST midnight of D in unix
    rows = []
    for h in HOURS:
        t0 = mid + h * 3600
        ask = bid = last = None; ask_t = bid_t = last_t = None; vol = 0.0
        for (t, p, q, buy) in trades:
            if t > t0: break
            last, last_t = p, t; vol += q
            if buy:
                ask, ask_t = p, t
                if bid is not None and bid >= p: bid = None
            else:
                bid, bid_t = p, t
                if ask is not None and ask <= p: ask = None
        rows.append(dict(series=series, ticker=meta["ticker"], day=day.date().isoformat(), stype=meta["strike_type"],
                         floor=meta.get("floor_strike"), cap=meta.get("cap_strike"), result=res["result"],
                         settle=res.get("expiration_value"), h=h, ask=ask, bid=bid, last=last,
                         ask_age=(t0 - ask_t) / 60 if ask_t else None, bid_age=(t0 - bid_t) / 60 if bid_t else None,
                         last_age=(t0 - last_t) / 60 if last_t else None, vol=vol))
    return rows

if __name__ == "__main__":
    jobs = []
    for s in LST:
        for d in sorted(os.listdir(ROOT / s)):
            if d >= LOCKBOX or d.startswith("_"): continue
            for f in os.listdir(ROOT / s / d):
                if f.endswith(".zst"): jobs.append((s, ROOT / s / d / f))
    print(len(jobs), "markets")
    with Pool(8) as p:
        out = [r for rows in p.imap_unordered(one, jobs, chunksize=20) for r in rows]
    df = pd.DataFrame(out)
    df.to_parquet(Path(__file__).parent / "snaps.parquet")
    print(df.shape)
