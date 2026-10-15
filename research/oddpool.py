"""Oddpool historical Kalshi order books (https://docs.oddpool.com/kalshi/orderbook.md): fetch and validate.

Oddpool stores 1-minute (or 5-minute) snapshots of each market's book (YES and NO bid ladders), from Mar 19 2026.
That is coarser than our own recordings (every delta), so before using it for maker backtests, `compare` rebuilds
our recorded book at each of Oddpool's snapshot times and reports how often best bid/ask and near-touch depth agree.

    python research/oddpool.py fetch   --market KXHIGHNY-26OCT14-B71.5 [--start 2026-10-13T14:00 --end ...]
    python research/oddpool.py compare --market KXHIGHNY-26OCT14-B71.5        (needs our recordings: trading server)

Key: ODDPOOL_API_KEY in .env (never committed). Free tier: 1 req/s, 1,000 requests/month, 200 snapshots per request.
Output: <data>/backfill/oddpool/<SERIES>/<ticker>.jsonl.zst, one snapshot per line as Oddpool returns it.
"""

import argparse
import glob
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from kalshi_lab import auth  # noqa: E402,F401  (loads .env)

DATA = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent
API = "https://api.oddpool.com/historical/kalshi/orderbook"


def _ms(s: str) -> int:
    return int(datetime.fromisoformat(s).replace(tzinfo=timezone.utc).timestamp() * 1000)


def fetch(market: str, start: str | None, end: str | None, granularity: str = "1m") -> list[dict]:
    key = os.environ.get("ODDPOOL_API_KEY")
    if not key:
        sys.exit("ODDPOOL_API_KEY is not set (.env)")
    params = {"market_id": market, "granularity": granularity, "limit": 200}
    if start:
        params["start_time"] = _ms(start)
    if end:
        params["end_time"] = _ms(end)
    out, n_req = [], 0
    with httpx.Client(timeout=30, headers={"X-API-Key": key}) as c:
        while True:
            r = c.get(API, params=params)
            n_req += 1
            if r.status_code == 429:
                time.sleep(float(r.headers.get("Retry-After", 2)))
                continue
            r.raise_for_status()
            d = r.json()
            out += d.get("snapshots", [])
            pg = d.get("pagination") or {}
            if not pg.get("has_more"):
                break
            params["pagination_key"] = pg["pagination_key"]
            time.sleep(1.05)  # free tier: 1 request/second
    out.sort(key=lambda s: s["timestamp"])
    import zstandard
    path = DATA / "backfill" / "oddpool" / market.split("-")[0] / f"{market}.jsonl.zst"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(zstandard.ZstdCompressor(level=6).compress("".join(json.dumps(s) + "\n" for s in out).encode()))
    print(f"{market}: {len(out)} snapshots in {n_req} requests -> {path}")
    return out


def _load_oddpool(market: str) -> list[dict]:
    import zstandard
    path = DATA / "backfill" / "oddpool" / market.split("-")[0] / f"{market}.jsonl.zst"
    return [json.loads(x) for x in zstandard.ZstdDecompressor().decompress(path.read_bytes(), max_output_size=2**31).splitlines()]


def _our_books(market: str, times_ms: list[int]):
    """Replay our recorded snapshot+deltas for `market`; yield (t_ms, yes_bids, no_bids) at each requested time."""
    import zstandard
    series = market.split("-")[0]
    files = sorted(glob.glob(str(DATA / "raw" / "kalshi_ws" / series / "*" / "*.jsonl.zst")))
    book = {"yes": {}, "no": {}}
    have, i, out = False, 0, []
    for f in files:
        for line in zstandard.ZstdDecompressor().stream_reader(open(f, "rb")).read().decode().splitlines():
            r = json.loads(line)
            m = r["m"] if isinstance(r["m"], dict) else json.loads(r["m"])
            t = m.get("type")
            if t in ("_connect", "_disconnect"):
                have = False  # a reconnect sends fresh snapshots; anything between is unknown
                continue
            msg = m.get("msg") or {}
            if msg.get("market_ticker") != market or t not in ("orderbook_snapshot", "orderbook_delta"):
                continue
            ts = r["t"] // 1_000_000
            while i < len(times_ms) and times_ms[i] <= ts:
                out.append((times_ms[i], dict(book["yes"]), dict(book["no"])) if have else (times_ms[i], None, None))
                i += 1
            if t == "orderbook_snapshot":
                book = {s: {p: float(q) for p, q in msg.get(f"{s}_dollars_fp", [])} for s in ("yes", "no")}
                have = True
            else:
                side, p = msg["side"], msg["price_dollars"]
                q = book[side].get(p, 0.0) + float(msg["delta_fp"])
                if q <= 1e-9:
                    book[side].pop(p, None)
                else:
                    book[side][p] = q
    while i < len(times_ms):
        out.append((times_ms[i], dict(book["yes"]), dict(book["no"])) if have else (times_ms[i], None, None))
        i += 1
    return out


def compare(market: str):
    snaps = _load_oddpool(market)
    ours = _our_books(market, [s["timestamp"] for s in snaps])
    n = agree_bid = agree_ask = 0
    depth_err = []
    for s, (t, yb, nb) in zip(snaps, ours):
        if yb is None:
            continue
        n += 1
        best_yb = max((float(p) for p in yb), default=None)
        best_ya = 1 - max((float(p) for p in nb), default=None) if nb else None
        o_yb, o_ya = s.get("best_yes_bid"), s.get("best_yes_ask")
        agree_bid += best_yb is not None and o_yb is not None and abs(best_yb - float(o_yb)) < 1e-6
        agree_ask += best_ya is not None and o_ya is not None and abs(best_ya - float(o_ya)) < 1e-6
        if best_yb is not None:
            od = {float(x["price"]): float(x["size"]) for x in s.get("yes_bids", [])}
            ours_top = yb.get(f"{best_yb:.4f}", 0.0)
            if od.get(best_yb) is not None and ours_top > 0:
                depth_err.append(abs(od[best_yb] - ours_top) / ours_top)
    print(f"{market}: {len(snaps)} Oddpool snapshots, {n} with our recorded book")
    if n:
        print(f"  best YES bid agrees {agree_bid / n:.0%}, best YES ask agrees {agree_ask / n:.0%}")
    if depth_err:
        import statistics
        print(f"  size at our best bid: median relative difference {statistics.median(depth_err):.1%}, "
              f"within 10% in {sum(e <= 0.1 for e in depth_err) / len(depth_err):.0%} of snapshots")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["fetch", "compare"])
    ap.add_argument("--market", required=True)
    ap.add_argument("--start")
    ap.add_argument("--end")
    ap.add_argument("--granularity", default="1m", choices=["1m", "5m"])
    a = ap.parse_args(argv)
    if a.cmd == "fetch":
        fetch(a.market, a.start, a.end, a.granularity)
    else:
        compare(a.market)


if __name__ == "__main__":
    main()
