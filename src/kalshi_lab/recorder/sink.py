"""Append-only raw event log.

Layout: <root>/<stream>/<YYYY-MM-DD>/<HH>.jsonl.zst (UTC hour of receipt), one line per message:
    {"t": <local receive time, ns>, "m": <raw message as received>}
Raw text is stored untouched so schema changes never lose data; normalization happens at replay.
Each flush closes a zstd frame, so a crash loses at most one flush interval and restarts append cleanly.
"""

import io
import time
from datetime import datetime, timezone
from pathlib import Path

import zstandard

EXT = ".jsonl.zst"


class _Stream:
    def __init__(self, path: Path, level: int):
        self.fh = open(path, "ab")
        self.cctx = zstandard.ZstdCompressor(level=level)
        self.buf = io.StringIO()

    def flush(self):
        data = self.buf.getvalue()
        if data:
            self.fh.write(self.cctx.compress(data.encode()))
            self.fh.flush()
            self.buf = io.StringIO()

    def close(self):
        self.flush()
        self.fh.close()


class Sink:
    def __init__(self, root: str | Path, level: int = 3):
        self.root = Path(root)
        self.level = level
        self._streams: dict[str, tuple[str, _Stream]] = {}
        self.counts: dict[str, int] = {}

    def write(self, stream: str, raw: str, recv_ns: int | None = None):
        recv_ns = recv_ns or time.time_ns()
        hour = datetime.fromtimestamp(recv_ns / 1e9, timezone.utc).strftime("%Y-%m-%d/%H")
        cur = self._streams.get(stream)
        if cur is None or cur[0] != hour:
            if cur:
                cur[1].close()
            path = self.root / stream / f"{hour}{EXT}"
            path.parent.mkdir(parents=True, exist_ok=True)
            cur = (hour, _Stream(path, self.level))
            self._streams[stream] = cur
        if "\n" in raw:  # some feeds terminate messages with newlines; JSON text never needs them
            raw = raw.replace("\n", "")
        cur[1].buf.write(f'{{"t":{recv_ns},"m":{raw}}}\n')
        self.counts[stream] = self.counts.get(stream, 0) + 1

    def flush(self):
        for _, s in self._streams.values():
            s.flush()

    def close(self):
        for _, s in self._streams.values():
            s.close()
        self._streams.clear()


def read_lines(path: str | Path):
    """Yield decoded lines from a (possibly multi-frame, possibly truncated) log file."""
    with open(path, "rb") as fh:
        reader = zstandard.ZstdDecompressor().stream_reader(fh, read_across_frames=True)
        text = io.TextIOWrapper(reader, encoding="utf-8")
        try:
            yield from text
        except zstandard.ZstdError:
            return  # truncated final frame from a crash
