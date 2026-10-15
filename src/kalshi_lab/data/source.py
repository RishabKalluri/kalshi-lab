"""Event sources for the engine. Each yields normalized events in timestamp order.

RecordedSource  replays what the recorder captured (full book + trades + spot).
BackfillSource  replays REST history (trades + 1m spot candles, no book), for coarse long-horizon tests.
"""

import heapq
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..core.types import Event
from ..recorder.sink import EXT, read_lines
from .normalize import parse


def _root(root) -> Path:
    return Path(root or os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser()


def _hours(start: datetime, end: datetime):
    h = start.replace(minute=0, second=0, microsecond=0)
    while h < end:
        yield h.strftime("%Y-%m-%d/%H")
        h += timedelta(hours=1)


def _stream_events(stream: str, files: list[Path], start_ns: int, end_ns: int):
    for f in files:
        for line in read_lines(f):
            d = json.loads(line)
            t = d["t"]
            if t < start_ns:
                continue
            if t >= end_ns:
                return
            yield from parse(stream, t, d["m"])


def merge(iters) -> "Iterator[Event]":
    """Merge per-stream iterators (each already time-ordered) into one time-ordered stream."""
    return heapq.merge(*iters, key=lambda e: e.ts)


class RecordedSource:
    """Replays recorded data from `start - warmup` so books/markets exist at `start`
    (pass `start` to Engine as start_ts so the strategy only sees data from `start`)."""

    def __init__(self, series: list[str], start: datetime, end: datetime, spot: list[str] | None = None,
                 root: str | None = None, warmup: timedelta = timedelta(minutes=20)):
        self.root = _root(root)
        self.series, self.end = series, end
        self.start = start - warmup
        self.spot = spot  # e.g. ['coinbase_btcusd']; None = every spot stream on disk

    def streams(self) -> list[str]:
        out = []
        for s in self.series:
            out += [f"kalshi_meta/{s}", f"kalshi_ws/{s}"]
        spot_dir = self.root / "spot"
        names = self.spot if self.spot is not None else sorted(p.name for p in spot_dir.glob("*") if p.is_dir())
        out += [f"spot/{n}" for n in names]
        return out

    def __iter__(self):
        s_ns, e_ns = int(self.start.timestamp() * 1e9), int(self.end.timestamp() * 1e9)
        # Include metadata from before `start` so markets that opened earlier are known.
        meta_start = self.start - timedelta(hours=1)
        iters = []
        for stream in self.streams():
            is_meta = stream.startswith("kalshi_meta")
            hours = _hours(meta_start if is_meta else self.start, self.end)
            files = [p for h in hours if (p := self.root / stream / f"{h}{EXT}").exists()]
            iters.append(_stream_events(stream, files, (s_ns - 3600 * 10**9) if is_meta else s_ns, e_ns))
        return merge(iters)


class BackfillSource:
    """Trades-only history written by `kalshi-lab backfill`. See data/backfill.py for layout."""

    def __init__(self, series: list[str], start: datetime, end: datetime, spot: list[str] | None = None,
                 root: str | None = None):
        self.root = _root(root).parent / "backfill"
        self.series, self.start, self.end, self.spot = series, start, end, spot

    def __iter__(self):
        s_ns, e_ns = int(self.start.timestamp() * 1e9), int(self.end.timestamp() * 1e9)
        iters = []
        day = self.start.date()
        days = []
        while day <= self.end.date():
            days.append(day.isoformat())
            day += timedelta(days=1)
        for s in self.series:
            files = sorted(p for d in days for p in (self.root / "kalshi" / s / d).glob(f"*{EXT}"))
            iters.append(_backfill_markets(files, s_ns, e_ns))
        spot_dir = self.root / "spot"
        names = self.spot if self.spot is not None else sorted(p.name for p in spot_dir.glob("*") if p.is_dir())
        # spot files are per UTC day: one starting at the (exclusive) end holds nothing in range; don't open it
        # (on the research server a lockbox-dated file isn't readable at all)
        last = (self.end - timedelta(microseconds=1)).date().isoformat()
        for n in names:
            files = [p for d in days if d <= last and (p := spot_dir / n / f"{d}{EXT}").exists()]
            iters.append(_stream_events(f"spot/{n}", files, s_ns, e_ns))
        return merge(iters)


def _backfill_markets(files, s_ns, e_ns):
    # Each file is one market: a 'discovered' meta line at open, trades in time order, a 'settled' meta line.
    for f in files:
        try:
            lines = [json.loads(line) for line in read_lines(f)]
        except PermissionError:
            # research server: lockbox-dated files are unreadable to development runs; the backtest already refuses
            # windows past the lockbox start, so such a file is one that starts after this window's end
            continue
        if not lines or lines[0]["t"] >= e_ns or lines[-1]["t"] < s_ns:
            continue
        for d in lines:
            m = d["m"]
            if m.get("event") == "discovered":
                # The REST row was fetched after settlement; hide the outcome until it happens.
                m = {**m, "market": {**m["market"], "result": "", "expiration_value": ""}}
                yield from parse("kalshi_meta/x", d["t"], m)
            elif m.get("event") == "settled":
                yield from parse("kalshi_meta/x", d["t"], m)
            elif s_ns <= d["t"] < e_ns:
                yield from parse("kalshi_ws/x", d["t"], m)


class BooksSource:
    """Historical order books (backfill/books, Predexon; see data/books.py) + trades and settlements (backfill/kalshi),
    so maker strategies get real queues on months of history, the same way RecordedSource replays our recordings.

    Markets overlap in time (weather brackets, sports games), so each market is its own time-ordered iterator, opened
    when the market opens and merged lazily. A market already open at `start` is fast-forwarded: its book is rebuilt
    from the file and handed to the engine as one snapshot at `start`."""

    LOOKAHEAD = timedelta(days=16)  # markets close up to ~2 weeks after they trade (sports); find them by close date

    def __init__(self, series: list[str], start: datetime, end: datetime, spot: list[str] | None = None,
                 root: str | None = None):
        self.root = _root(root).parent / "backfill"
        self.series, self.start, self.end, self.spot = series, start, end, spot

    def _markets(self):
        s_ns, e_ns = int(self.start.timestamp() * 1e9), int(self.end.timestamp() * 1e9)
        day, last = self.start.date(), (self.end + self.LOOKAHEAD).date()
        out = []
        while day <= last:
            for s in self.series:
                for f in sorted((self.root / "kalshi" / s / day.isoformat()).glob(f"*{EXT}")):
                    try:
                        first = json.loads(next(iter(read_lines(f))))
                    except (StopIteration, PermissionError):
                        continue
                    if first["t"] >= e_ns:
                        continue
                    books = self.root / "books" / s / day.isoformat() / f.name
                    out.append((first["t"], f, books if books.exists() else None))
            day += timedelta(days=1)
        return s_ns, e_ns, sorted(out, key=lambda x: x[0])

    @staticmethod
    def _market(trades: Path, books: Path | None, s_ns: int, e_ns: int):
        def trade_events():
            for line in read_lines(trades):
                d = json.loads(line)
                m = d["m"]
                if m.get("event") == "discovered":
                    m = {**m, "market": {**m["market"], "result": "", "expiration_value": ""}}
                    yield from parse("kalshi_meta/x", d["t"], m)
                elif m.get("event") == "settled":
                    if d["t"] < e_ns:
                        yield from parse("kalshi_meta/x", d["t"], m)
                    return
                elif s_ns <= d["t"] < e_ns:
                    yield from parse("kalshi_ws/x", d["t"], m)

        def book_events():
            if books is None:
                return
            book, ticker, caught_up = {"yes": {}, "no": {}}, None, False
            for line in read_lines(books):
                d = json.loads(line)
                t, m = d["t"], d["m"]
                if t >= e_ns:
                    break
                if t < s_ns:  # before the window: just rebuild the book
                    msg = m.get("msg", {})
                    ticker = msg.get("market_ticker", ticker)
                    if m.get("type") == "orderbook_snapshot":
                        book = {"yes": dict(msg.get("yes_dollars_fp") or []), "no": dict(msg.get("no_dollars_fp") or [])}
                    elif m.get("type") == "orderbook_delta":
                        lv = book[msg["side"]]
                        q = float(lv.get(msg["price_dollars"], 0)) + float(msg["delta_fp"])
                        if q > 1e-9:
                            lv[msg["price_dollars"]] = f"{q:.2f}"
                        else:
                            lv.pop(msg["price_dollars"], None)
                    continue
                if not caught_up and ticker is not None:
                    yield from parse("kalshi_ws/x", s_ns, {"type": "orderbook_snapshot", "msg": {
                        "market_ticker": ticker, "yes_dollars_fp": list(book["yes"].items()),
                        "no_dollars_fp": list(book["no"].items())}})
                caught_up = True
                yield from parse("kalshi_ws/x", t, m)
            if not caught_up and ticker is not None and s_ns < e_ns:  # open at `start` but no change in the window
                yield from parse("kalshi_ws/x", s_ns, {"type": "orderbook_snapshot", "msg": {
                    "market_ticker": ticker, "yes_dollars_fp": list(book["yes"].items()),
                    "no_dollars_fp": list(book["no"].items())}})

        # trades file first on ties: the market's discovery precedes its first book
        return heapq.merge(trade_events(), book_events(), key=lambda e: e.ts)

    def __iter__(self):
        s_ns, e_ns, markets = self._markets()
        iters = [self._lazy(markets, s_ns, e_ns)]
        spot_dir = self.root / "spot"
        if self.spot:
            days, day = [], self.start.date()
            while day <= self.end.date():
                days.append(day.isoformat())
                day += timedelta(days=1)
            for n in self.spot:
                files = [p for d in days if (p := spot_dir / n / f"{d}{EXT}").exists()]
                iters.append(_stream_events(f"spot/{n}", files, s_ns, e_ns))
        return merge(iters)

    def _lazy(self, markets, s_ns, e_ns):
        """Merge per-market iterators, opening each only when the replay reaches its first event."""
        heap, i, n = [], 0, 0
        while heap or i < len(markets):
            while i < len(markets) and (not heap or markets[i][0] <= heap[0][0]):
                _, trades, books = markets[i]
                i += 1
                it = self._market(trades, books, s_ns, e_ns)
                e = next(it, None)
                if e is not None:
                    heapq.heappush(heap, (e.ts, n, e, it))
                    n += 1
            if not heap:
                continue
            _, _, e, it = heapq.heappop(heap)
            yield e
            nxt = next(it, None)
            if nxt is not None:
                heapq.heappush(heap, (nxt.ts, n, nxt, it))
                n += 1
