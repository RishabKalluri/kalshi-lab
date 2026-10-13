import argparse
import asyncio
import logging
import os
import signal
from pathlib import Path

from .. import auth  # noqa: F401  (loads .env)
from .config import GROUPS, RECORD_DEFAULT, SERIES
from .kalshi import KalshiRecorder
from .sink import Sink
from .spot import run_feed

log = logging.getLogger("recorder")


async def flusher(sink: Sink, flush_s: float = 5, report_s: float = 60):
    prev: dict[str, int] = {}
    n = 0
    while True:
        await asyncio.sleep(flush_s)
        sink.flush()
        n += 1
        if n % int(report_s / flush_s) == 0:
            rates = {k: v - prev.get(k, 0) for k, v in sink.counts.items()}
            prev = dict(sink.counts)
            log.info("msgs/%ss: %s", int(report_s), rates)


async def amain(series: list[str], root: str):
    sink = Sink(root)
    tasks = [flusher(sink)]
    feeds = set()
    for s in series:
        tasks.append(KalshiRecorder(s, sink).run())
        feeds.update(SERIES.get(s, []))
    tasks += [run_feed(f, sink) for f in sorted(feeds)]
    log.info("recording %s + %s -> %s", series, sorted(feeds), root)

    loop = asyncio.get_running_loop()
    gathered = asyncio.gather(*tasks)
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, gathered.cancel)
    try:
        await gathered
    except asyncio.CancelledError:
        log.info("shutting down")
    finally:
        sink.close()


def main(argv=None):
    p = argparse.ArgumentParser(description="Record Kalshi series + underlying spot feeds")
    p.add_argument("--series", nargs="+", default=RECORD_DEFAULT, help=f"known: {list(SERIES)}")
    p.add_argument("--group", choices=list(GROUPS), help="record a group of series instead (own unit per group)")
    p.add_argument("--weather", action="store_true", help="same as --group weather")
    p.add_argument("--root", default=os.environ.get("KALSHI_DATA_ROOT", "data/raw"))
    args = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    group = "weather" if args.weather else args.group
    asyncio.run(amain(GROUPS[group] if group else args.series, str(Path(args.root).expanduser())))
