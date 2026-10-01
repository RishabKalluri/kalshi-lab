"""Download REST history into <data>/backfill.

Kalshi keeps recent data on /markets + /markets/trades and older data on /historical/*
(the split point comes from /historical/cutoff). Order books are not available historically.

Layout (same zstd JSONL line format as the recorder, with t = exchange time):
  backfill/kalshi/<SERIES>/<close-date>/<market>.jsonl.zst   meta, trades..., settled meta
  backfill/spot/coinbase_<sym>/<date>.jsonl.zst              1-minute candles as synthetic ticks
  backfill/spot/binance_<sym>/<date>.jsonl.zst               1-second candles (USDT pair) as ticks
  backfill/flow/<source>/<date>.parquet                      order flow per second (backfill_flow below)

Binance history comes from its public market-data mirror (data-api.binance.vision). It's a
USDT pair, so it carries a small, slowly-varying basis to BRTI; strategies should correct for
that against the market's strike (see strategies/_archive/models.py).
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx

from ..recorder.sink import EXT, Sink
from ..rest import KalshiREST
from .normalize import iso_ns

log = logging.getLogger("backfill")

from ..recorder.config import MARKETS  # noqa: E402  (per-series spot history sources live there)


def _write_atomic(path: Path, lines: list[tuple[int, str]]):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")  # per-process, so parallel backfills never clash
    tmp.unlink(missing_ok=True)
    import zstandard
    body = "".join(f'{{"t":{t},"m":{m}}}\n' for t, m in lines)
    tmp.write_bytes(zstandard.ZstdCompressor(level=6).compress(body.encode()))
    tmp.rename(path)


def settled_markets(rest: KalshiREST, series: str, start: datetime, end: datetime, cutoff: datetime):
    """Settled markets closing in [start, end). Before `cutoff` they live on /historical/markets (which
    ignores close-time filters, so we filter here); after it on /markets, which silently truncates wide
    windows, so we ask week by week."""
    in_range = lambda m: start <= datetime.fromisoformat(m["close_time"].replace("Z", "+00:00")) < end
    seen = set()
    if start < cutoff:
        for m in rest.paginate("/historical/markets", "markets", limit=1000, series_ticker=series,
                               min_close_ts=int(start.timestamp()), max_close_ts=int(min(end, cutoff).timestamp())):
            if in_range(m) and m["ticker"] not in seen:
                seen.add(m["ticker"])
                yield m, True
    t = max(start, cutoff)
    while t < end:
        t2 = min(t + timedelta(days=7), end)
        for m in rest.paginate("/markets", "markets", limit=1000, status="settled", series_ticker=series,
                               min_close_ts=int(t.timestamp()), max_close_ts=int(t2.timestamp())):
            if in_range(m) and m["ticker"] not in seen:
                seen.add(m["ticker"])
                yield m, False
        t = t2


def backfill_kalshi(rest: KalshiREST, root: Path, series: str, start: datetime, end: datetime):
    cutoff = datetime.fromisoformat(rest.get("/historical/cutoff")["trades_created_ts"].replace("Z", "+00:00"))
    markets = sorted(settled_markets(rest, series, start, end, cutoff), key=lambda x: x[0]["close_time"])
    log.info("%s: %d settled markets in range", series, len(markets))
    for i, (m, historical) in enumerate(markets):
        close = m["close_time"][:10]
        path = root / "kalshi" / series / close / f"{m['ticker']}{EXT}"
        if path.exists():
            continue
        if not m.get("result"):
            continue
        t0 = time.time()
        try:
            trades = list(rest.paginate("/historical/trades" if historical else "/markets/trades", "trades",
                                        ticker=m["ticker"], limit=1000))
        except Exception:
            log.exception("%s: failed, skipping (re-run backfill to retry)", m["ticker"])
            continue
        trades.sort(key=lambda tr: tr["created_time"])
        open_ns = iso_ns(m["open_time"])
        opened = {**m, "result": "", "expiration_value": ""}
        lines = [(open_ns, json.dumps({"event": "discovered", "market": opened}))]
        for tr in trades:
            # Reshape to the websocket trade message so the same parser handles both.
            msg = {"type": "trade", "msg": {"market_ticker": tr["ticker"], "yes_price_dollars": tr["yes_price_dollars"],
                                            "count_fp": tr["count_fp"], "taker_side": tr["taker_side"]}}
            lines.append((iso_ns(tr["created_time"]), json.dumps(msg)))
        close_ns = iso_ns(m["close_time"])
        lines.append((close_ns + 1, json.dumps({"event": "settled", "market": m})))
        _write_atomic(path, lines)
        log.info("[%d/%d] %s %s trades=%d (%.1fs)", i + 1, len(markets), m["ticker"], m["result"], len(trades),
                 time.time() - t0)


def backfill_coinbase(root: Path, product: str, start: datetime, end: datetime):
    name = f"coinbase_{product.replace('-', '').lower()}"
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    with httpx.Client(timeout=15) as client:
        while day < end:
            path = root / "spot" / name / f"{day.date().isoformat()}{EXT}"
            nxt = day + timedelta(days=1)
            if not path.exists() and nxt <= datetime.now(timezone.utc):
                rows = []
                t = day
                while t < nxt:
                    t2 = min(t + timedelta(minutes=300), nxt)
                    r = client.get(f"https://api.exchange.coinbase.com/products/{product}/candles",
                                   params={"granularity": 60, "start": t.isoformat(), "end": t2.isoformat()})
                    r.raise_for_status()
                    rows += r.json()
                    t = t2
                    time.sleep(0.15)
                rows = sorted({r[0]: r for r in rows}.values())
                # Candle [time, low, high, open, close, vol] -> a tick at the minute's end with the close.
                lines = [((r[0] + 60) * 10**9, json.dumps({"type": "ticker", "price": r[4]})) for r in rows]
                _write_atomic(path, lines)
                log.info("%s %s: %d candles", name, day.date(), len(rows))
            day = nxt


def backfill_binance_1s(root: Path, symbol: str, start: datetime, end: datetime):
    name = f"binance_{symbol.lower()}"
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    with httpx.Client(timeout=20) as client:
        while day < end:
            path = root / "spot" / name / f"{day.date().isoformat()}{EXT}"
            nxt = day + timedelta(days=1)
            if not path.exists() and nxt <= datetime.now(timezone.utc):
                rows, t = [], int(day.timestamp() * 1000)
                stop = int(nxt.timestamp() * 1000)
                while t < stop:
                    for attempt in range(6):
                        try:
                            r = client.get("https://data-api.binance.vision/api/v3/klines",
                                           params={"symbol": symbol, "interval": "1s", "startTime": t,
                                                   "endTime": stop - 1, "limit": 1000})
                            r.raise_for_status()
                            break
                        except (httpx.TransportError, httpx.HTTPStatusError) as e:
                            log.warning("binance %s: %r, retrying", symbol, e)
                            time.sleep(2 ** attempt)
                    else:
                        raise RuntimeError(f"binance {symbol}: giving up at {t}")
                    batch = r.json()
                    if not batch:
                        break
                    rows += batch
                    t = batch[-1][0] + 1000
                # Kline [open_ms, o, h, l, c, ...] -> a tick at the second's end with the close.
                lines = [((k[0] + 1000) * 10**6, json.dumps({"type": "ticker", "price": float(k[4])})) for k in rows]
                _write_atomic(path, lines)
                log.info("%s %s: %d seconds", name, day.date(), len(rows))
            day = nxt


def backfill_okx(root: Path, inst: str, start: datetime, end: datetime, bar: str = "1m"):
    """OKX history-candles, 100 bars per request (limit 20 req / 2 s). 1s bars cost ~7 min/day; 1m ~5 s/day."""
    step = {"1s": 1000, "1m": 60_000}[bar]
    name = f"okx_{inst.replace('-', '').lower()}" + ("" if bar == "1s" else f"_{bar}")
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    with httpx.Client(timeout=20) as client:
        while day < end:
            path = root / "spot" / name / f"{day.date().isoformat()}{EXT}"
            nxt = day + timedelta(days=1)
            if not path.exists() and nxt <= datetime.now(timezone.utc):
                rows = {}
                after = int(nxt.timestamp() * 1000)  # OKX pages backwards: returns bars older than `after`
                stop = int(day.timestamp() * 1000)
                while after > stop:
                    for attempt in range(6):
                        try:
                            r = client.get("https://www.okx.com/api/v5/market/history-candles",
                                           params={"instId": inst, "bar": bar, "after": after, "limit": 100})
                            r.raise_for_status()
                            data = r.json()["data"]
                            break
                        except (httpx.TransportError, httpx.HTTPStatusError, KeyError) as e:
                            log.warning("okx %s: %r, retrying", inst, e)
                            time.sleep(2 ** attempt)
                    else:
                        raise RuntimeError(f"okx {inst}: giving up at {after}")
                    if not data:
                        break
                    for k in data:
                        ts = int(k[0])
                        if ts >= stop:
                            rows[ts] = float(k[4])
                    after = int(data[-1][0])
                    time.sleep(0.1)
                lines = [((ts + step) * 10**6, json.dumps({"type": "ticker", "price": px})) for ts, px in sorted(rows.items())]
                _write_atomic(path, lines)
                log.info("%s %s: %d seconds", name, day.date(), len(rows))
            day = nxt


FLOW_COLS = ["t", "px", "buy", "sell", "n", "max_trade"]


def _flow_write(path: Path, df):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(f".{os.getpid()}.tmp")
    df[FLOW_COLS].to_parquet(tmp, index=False, compression="zstd")
    tmp.rename(path)


def _get_zip(client: httpx.Client, url: str) -> bytes | None:
    """A daily archive file, or None if it isn't published (yet)."""
    for attempt in range(6):
        try:
            r = client.get(url)
            if r.status_code == 404:
                return None
            r.raise_for_status()
            return r.content
        except (httpx.TransportError, httpx.HTTPStatusError) as e:
            log.warning("%s: %r, retrying", url, e)
            time.sleep(2 ** attempt)
    raise RuntimeError(f"giving up on {url}")


def _csv_from_zip(blob: bytes, **kw):
    import io
    import zipfile

    import pandas as pd
    with zipfile.ZipFile(io.BytesIO(blob)) as z:
        with z.open(z.namelist()[0]) as fh:
            return pd.read_csv(fh, **kw)


def backfill_binance_flow(root: Path, symbol: str, start: datetime, end: datetime, client: httpx.Client):
    """Binance spot 1s klines from the public archive (data.binance.vision): volume and taker-buy volume per
    second. Taker sells = volume - taker buys. Reachable from US IPs (live: data-stream.binance.vision)."""
    import pandas as pd
    name = f"binance_{symbol.lower()}"
    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        d = day.date().isoformat()
        path = root / "flow" / name / f"{d}.parquet"
        if not path.exists() and day + timedelta(days=1) <= datetime.now(timezone.utc):
            blob = _get_zip(client, f"https://data.binance.vision/data/spot/daily/klines/{symbol}/1s/{symbol}-1s-{d}.zip")
            if blob is None:
                log.info("%s %s: not published yet", name, d)
            else:
                k = _csv_from_zip(blob, header=None, usecols=[0, 4, 5, 8, 9])
                k.columns = ["open", "px", "vol", "n", "buy"]
                # open time is in ms before 2025 and in us after; normalise to the second the candle covers
                ts = k["open"].astype("int64")
                t = (ts // 1_000_000).where(ts > 10**14, ts // 1000)
                df = pd.DataFrame({"t": t + 1, "px": k["px"], "buy": k["buy"], "sell": k["vol"] - k["buy"],
                                   "n": k["n"].astype("int32"), "max_trade": float("nan")})
                _flow_write(path, df[k["n"] > 0])
                log.info("%s %s: %d active seconds", name, d, int((k["n"] > 0).sum()))
        day += timedelta(days=1)


def backfill_okx_flow(root: Path, inst: str, start: datetime, end: datetime, client: httpx.Client):
    """OKX perpetual trades from its public archive, aggregated per second: taker buy/sell volume (base
    currency), trade count, largest trade, last price. OKX's daily files run 16:00-16:00 UTC (UTC+8 days),
    so UTC day D is the end of file D plus the start of file D+1."""
    import pandas as pd
    name = f"okx_{inst.replace('-', '').lower()}"
    ct_val = float(client.get("https://www.okx.com/api/v5/public/instruments",
                              params={"instType": "SWAP", "instId": inst}).json()["data"][0]["ctVal"])
    cache: dict = {}

    def okx_file(d):  # per-second aggregate of OKX file d (a date), or None if unpublished
        if d not in cache:
            ds = d.isoformat()
            blob = _get_zip(client, f"https://static.okx.com/cdn/okex/traderecords/trades/daily/{ds.replace('-', '')}/"
                                    f"{inst}-trades-{ds}.zip")
            if blob is None:
                cache[d] = None
            else:
                tr = _csv_from_zip(blob, usecols=["side", "price", "size", "created_time"])
                tr["t"] = tr["created_time"] // 1000 + 1  # the second ending at t, like the 1s spot candles
                tr["q"] = tr["size"] * ct_val
                tr["b"] = tr["q"].where(tr["side"] == "buy", 0.0)
                tr["s"] = tr["q"] - tr["b"]
                g = tr.groupby("t")
                cache[d] = pd.DataFrame({"px": g["price"].last(), "buy": g["b"].sum(), "sell": g["s"].sum(),
                                         "n": g.size().astype("int32"), "max_trade": g["q"].max()}).reset_index()
            for old in [k for k in cache if k < d - timedelta(days=1)]:
                del cache[old]
        return cache[d]

    day = start.replace(hour=0, minute=0, second=0, microsecond=0)
    while day < end:
        path = root / "flow" / name / f"{day.date().isoformat()}.parquet"
        nxt = day + timedelta(days=1)
        if not path.exists() and nxt + timedelta(hours=8) <= datetime.now(timezone.utc):
            a, b = okx_file(day.date()), okx_file(nxt.date())
            if a is None or b is None:
                log.info("%s %s: not published yet", name, day.date())
            else:
                lo, hi = int(day.timestamp()), int(nxt.timestamp())
                df = pd.concat([a, b])
                df = df[(df["t"] > lo) & (df["t"] <= hi)]
                _flow_write(path, df)
                log.info("%s %s: %d active seconds", name, day.date(), len(df))
        day = nxt


def backfill_flow(root: Path, series: str, start: datetime, end: datetime):
    """Order-flow history for a series' `flow` sources (recorder/config.py). Written to
    backfill/flow/<source>/<date>.parquet, one row per second with trades:
      t          unix second the row covers (trades in (t-1, t])
      px         last trade price
      buy, sell  taker buy / taker sell volume in the base coin
      n          number of trades
      max_trade  largest single trade in the base coin (OKX only; NaN for Binance klines)
    Load with kalshi_lab.data.flow.load_flow."""
    src = MARKETS.get(series, {}).get("flow", {})
    with httpx.Client(timeout=60) as client:
        if "binance" in src:
            backfill_binance_flow(root, src["binance"], start, end, client)
        if "okx" in src:
            backfill_okx_flow(root, src["okx"], start, end, client)


def main(argv=None):
    p = argparse.ArgumentParser(description="Backfill settled Kalshi markets (trades) + Coinbase 1m candles")
    p.add_argument("--series", nargs="+", default=["KXBTC15M"])
    p.add_argument("--days", type=float, default=7, help="how far back from now")
    p.add_argument("--start", help="ISO date/time (UTC), overrides --days")
    p.add_argument("--end", help="ISO date/time (UTC), default now")
    p.add_argument("--only", choices=["kalshi", "spot", "flow"], help="only backfill one kind of data")
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    end = datetime.fromisoformat(args.end).replace(tzinfo=timezone.utc) if args.end else datetime.now(timezone.utc)
    start = (datetime.fromisoformat(args.start).replace(tzinfo=timezone.utc) if args.start
             else end - timedelta(days=args.days))
    root = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
    rest = KalshiREST()
    for s in args.series:
        if args.only in (None, "spot"):
            bs = MARKETS.get(s, {}).get("backfill_spot", {})
            if "binance" in bs:
                backfill_binance_1s(root, bs["binance"], start, end)
            if "okx" in bs:
                backfill_okx(root, bs["okx"], start, end, bar="1m")
            if "coinbase" in bs:
                backfill_coinbase(root, bs["coinbase"], start, end)
        if args.only in (None, "flow"):
            backfill_flow(root, s, start, end)
        if args.only in (None, "kalshi"):
            backfill_kalshi(rest, root, s, start, end)
