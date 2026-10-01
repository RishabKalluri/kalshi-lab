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
        for n in names:
            files = [p for d in days if (p := spot_dir / n / f"{d}{EXT}").exists()]
            iters.append(_stream_events(f"spot/{n}", files, s_ns, e_ns))
        return merge(iters)


def _backfill_markets(files, s_ns, e_ns):
    # Each file is one market: a 'discovered' meta line at open, trades in time order, a 'settled' meta line.
    for f in files:
        lines = [json.loads(line) for line in read_lines(f)]
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
