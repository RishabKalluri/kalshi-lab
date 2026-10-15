"""Historical Kalshi order books from Predexon (free, unlimited endpoint; every book change since 2026-01-07).

GET https://api.predexon.com/v2/kalshi/orderbooks returns the full book (YES bids, YES asks, whole cents) each time it
changed. Checked against our own recordings (KXHIGHNY-26OCT13-B71.5, 4 h, 10,958 snapshots): best bid identical
98.1%, best ask 98.5%, size at the best bid within 5% 96.8%.

Each market is stored like a recording, so the same parser handles both: the first book as an `orderbook_snapshot`
(YES bids and NO bids; a YES ask at p is a NO bid at 100-p), then one `orderbook_delta` per level that changed between
consecutive books. Trades are not here: they are in backfill/kalshi (exact times and taker side).

  backfill/books/<SERIES>/<close-date>/<ticker>.jsonl.zst

    kalshi-lab books-download --series KXHIGHNY KXHIGHLAX ... [--start 2026-01-07] [--end ...] [--rps 1] [--workers 4]

The market list comes from backfill/kalshi (markets that traded), else Kalshi's settled-markets listing. Resumable:
finished markets are skipped. Key: PREDEXON_API_KEY (env or .env).
"""

import argparse
import asyncio
import json
import logging
import os
import random
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from .backfill import EXT, _write_atomic

log = logging.getLogger("books")
API = "https://api.predexon.com/v2/kalshi/orderbooks"
FIRST = datetime(2026, 1, 7, tzinfo=timezone.utc)
DATA = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent


def _ns(ms: int) -> int:
    return int(ms) * 1_000_000


def _ladders(s: dict) -> dict:
    """Predexon snapshot -> {('yes'|'no', cents): size}."""
    out = {("yes", int(x["price"])): float(x["size"]) for x in s.get("yes_bids") or []}
    out.update({("no", 100 - int(x["price"])): float(x["size"]) for x in s.get("yes_asks") or []})
    return out


def _fp(cents: int) -> str:
    return f"{cents / 100:.4f}"


def convert(ticker: str, snaps: list[dict]) -> list[tuple[int, str]]:
    """Snapshots -> recorder-style lines (t_ns, message json): one snapshot, then per-level deltas."""
    lines, prev = [], None
    for s in snaps:
        cur = _ladders(s)
        t = _ns(s["timestamp"])
        if prev is None:
            msg = {"market_ticker": ticker, "source": "predexon",
                   "yes_dollars_fp": [[_fp(p), f"{q:.2f}"] for (side, p), q in sorted(cur.items()) if side == "yes"],
                   "no_dollars_fp": [[_fp(p), f"{q:.2f}"] for (side, p), q in sorted(cur.items()) if side == "no"]}
            lines.append((t, json.dumps({"type": "orderbook_snapshot", "msg": msg})))
        else:
            for key in sorted(set(cur) | set(prev)):
                d = cur.get(key, 0.0) - prev.get(key, 0.0)
                if abs(d) > 1e-9:
                    lines.append((t, json.dumps({"type": "orderbook_delta", "msg": {
                        "market_ticker": ticker, "side": key[0], "price_dollars": _fp(key[1]), "delta_fp": f"{d:.2f}"}})))
        prev = cur
    return lines


class Limiter:
    def __init__(self, rps: float):
        self.gap, self.next = 1.0 / rps, 0.0
        self.lock = asyncio.Lock()

    async def wait(self):
        async with self.lock:
            now = time.monotonic()
            self.next = max(self.next, now)
            delay = self.next - now
            self.next += self.gap
        if delay > 0:
            await asyncio.sleep(delay)


async def fetch_market(client: httpx.AsyncClient, lim: Limiter, ticker: str, start_ms: int, end_ms: int) -> list[dict]:
    snaps, key = [], None
    while True:
        params = dict(ticker=ticker, start_time=start_ms, end_time=end_ms, limit=2000)
        if key:
            params["pagination_key"] = key
        for attempt in range(8):
            await lim.wait()
            try:
                r = await client.get(API, params=params)
            except httpx.TransportError as e:
                log.warning("%s: %r, retrying", ticker, e)
                await asyncio.sleep(2 ** attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                await asyncio.sleep(float(r.headers.get("Retry-After") or 2 ** attempt) + random.random())
                continue
            r.raise_for_status()
            break
        else:
            raise RuntimeError(f"{ticker}: gave up after retries")
        d = r.json()
        snaps += d.get("snapshots") or []
        pg = d.get("pagination") or {}
        key = pg.get("pagination_key")
        if not pg.get("has_more") or not key:
            return snaps


def markets_for(series: str, start: datetime, end: datetime) -> list[tuple[str, int, int, str]]:
    """(ticker, open ms, close ms, close date) for markets that traded, from backfill/kalshi, else Kalshi's listing."""
    out = []
    root = DATA / "backfill" / "kalshi" / series
    files = sorted(root.glob(f"*/*{EXT}")) if root.is_dir() else []
    if files:
        import zstandard
        for f in files:
            if not (start.strftime("%Y-%m-%d") <= f.parent.name <= end.strftime("%Y-%m-%d")):
                continue
            with zstandard.ZstdDecompressor().stream_reader(open(f, "rb")) as rd:
                first = rd.read(65536).decode(errors="ignore").split("\n", 1)[0]
            m = json.loads(first)["m"]["market"]
            out.append((m["ticker"], _ms(m["open_time"]), _ms(m["close_time"]), f.parent.name))
        return out
    from ..rest import KalshiREST
    from .backfill import settled_markets
    rest = KalshiREST(anonymous=True)
    cutoff = datetime.fromisoformat(rest.get("/historical/cutoff")["trades_created_ts"].replace("Z", "+00:00"))
    for m, _ in settled_markets(rest, series, start, end, cutoff):
        if float(m.get("volume_fp") or 0) > 0:
            out.append((m["ticker"], _ms(m["open_time"]), _ms(m["close_time"]), m["close_time"][:10]))
    return out


def _ms(iso: str) -> int:
    return int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000)


async def run(series: list[str], start: datetime, end: datetime, rps: float, workers: int, limit: int | None):
    key = os.environ.get("PREDEXON_API_KEY")
    if not key:
        raise SystemExit("PREDEXON_API_KEY not set")
    jobs = []
    for s in series:
        ms = markets_for(s, start, end)
        todo = [m for m in ms if not (DATA / "backfill" / "books" / s / m[3] / f"{m[0]}{EXT}").exists()]
        log.info("%s: %d markets in range, %d to download", s, len(ms), len(todo))
        jobs += [(s, *m) for m in todo]
    jobs = jobs[:limit] if limit else jobs
    lim, q = Limiter(rps), asyncio.Queue()
    for j in jobs:
        q.put_nowait(j)
    stats = dict(done=0, snaps=0, failed=0, t0=time.time())
    floor = int(FIRST.timestamp() * 1000)
    cap = int((datetime.now(timezone.utc) - timedelta(days=1)).timestamp() * 1000)

    async def worker(client):
        while not q.empty():
            s, ticker, o, c, day = q.get_nowait()
            try:
                snaps = await fetch_market(client, lim, ticker, max(o, floor), min(c + 3600_000, cap))
                path = DATA / "backfill" / "books" / s / day / f"{ticker}{EXT}"
                lines = convert(ticker, snaps) or [(_ns(c), json.dumps({"type": "_empty", "msg": {"market_ticker": ticker}}))]
                await asyncio.to_thread(_write_atomic, path, lines)
                stats["done"] += 1
                stats["snaps"] += len(snaps)
            except Exception:
                stats["failed"] += 1
                log.exception("%s: failed (re-run to retry)", ticker)
            n = stats["done"] + stats["failed"]
            if n % 25 == 0 or n == len(jobs):
                el = time.time() - stats["t0"]
                log.info("[%d/%d] %d snapshots, %d failed, %.1f markets/min, ETA %.0f min", n, len(jobs), stats["snaps"],
                         stats["failed"], 60 * n / el, (len(jobs) - n) / max(n / el, 1e-9) / 60)

    async with httpx.AsyncClient(timeout=60, headers={"x-api-key": key, "User-Agent": "kalshi-lab/1.0 (research)"},
                                 limits=httpx.Limits(max_connections=workers)) as client:
        await asyncio.gather(*[worker(client) for _ in range(workers)])
    log.info("done: %d markets, %d snapshots, %d failed", stats["done"], stats["snaps"], stats["failed"])


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab books-download", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--series", nargs="+", required=True)
    ap.add_argument("--start", default=FIRST.strftime("%Y-%m-%d"))
    ap.add_argument("--end", default=datetime.now(timezone.utc).strftime("%Y-%m-%d"))
    ap.add_argument("--rps", type=float, default=1.0, help="requests per second (free tier 1, Pro 100)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--limit", type=int, help="only the first N markets (testing)")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    from .. import auth  # noqa: F401  (loads .env)
    start = datetime.fromisoformat(a.start).replace(tzinfo=timezone.utc)
    end = datetime.fromisoformat(a.end).replace(tzinfo=timezone.utc)
    asyncio.run(run(a.series, max(start, FIRST), end, a.rps, a.workers, a.limit))
