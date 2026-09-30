"""Live event source: the recorder's feed handlers, pointed at a queue instead of disk.

Yields the same normalized events as RecordedSource (so strategies can't tell the difference),
plus a Timer event whenever the feed is quiet so the engine clock keeps moving.
"""

import asyncio
import logging
import queue
import threading
import time

from ..core.types import Timer
from ..data.normalize import parse
from ..recorder.config import SERIES
from ..recorder.kalshi import KalshiRecorder
from ..recorder.spot import run_feed

log = logging.getLogger("live")


class QueueSink:
    """Sink-compatible writer that normalizes messages and hands events to the engine thread."""

    def __init__(self, q: queue.Queue, tee=None):
        self.q = q
        self.tee = tee  # optional real Sink to also record to disk
        self.counts: dict[str, int] = {}

    def write(self, stream: str, raw: str, recv_ns: int | None = None):
        recv_ns = recv_ns or time.time_ns()
        if self.tee is not None:
            self.tee.write(stream, raw, recv_ns)
        try:
            for ev in parse(stream, recv_ns, raw):
                self.q.put(ev)
        except Exception:
            log.exception("failed to parse %s message: %.200s", stream, raw)
        self.counts[stream] = self.counts.get(stream, 0) + 1

    def flush(self):
        if self.tee is not None:
            self.tee.flush()

    def close(self):
        if self.tee is not None:
            self.tee.close()


class LiveSource:
    def __init__(self, series: list[str], spot: list[str] | None = None, idle_ms: int = 200):
        self.series = series
        self.feeds = sorted({f for s in series for f in SERIES.get(s, [])}) if spot is None else spot
        self.q: queue.Queue = queue.Queue()
        self.sink = QueueSink(self.q)
        self.idle_s = idle_ms / 1000
        self.stop = threading.Event()
        self._loop = None
        self._task = None

    def _run(self):
        async def main():
            self._loop = asyncio.get_running_loop()
            self._task = asyncio.gather(*[KalshiRecorder(s, self.sink).run() for s in self.series],
                                        *[run_feed(f, self.sink) for f in self.feeds])
            try:
                await self._task
            except asyncio.CancelledError:
                pass

        asyncio.run(main())

    def __iter__(self):
        thread = threading.Thread(target=self._run, daemon=True, name="live-feeds")
        thread.start()
        log.info("live feeds: %s + %s", self.series, self.feeds)
        last = time.time_ns()
        while not self.stop.is_set():
            try:
                ev = self.q.get(timeout=self.idle_s)
            except queue.Empty:
                yield Timer(time.time_ns())
                continue
            # Merge order across feeds is arrival order; clamp so time never goes backwards.
            if ev.ts < last:
                ev.ts = last
            last = ev.ts
            yield ev
        if self._loop is not None and self._task is not None:
            self._loop.call_soon_threadsafe(self._task.cancel)
        thread.join(timeout=5)
