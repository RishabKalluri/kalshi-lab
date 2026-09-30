"""Recent spot history from the recorder's files, so live/paper strategies don't need a warm-up
period after a restart. Produces the same per-second composite as ctx.spot(): the median of each
source's latest price, ignoring sources older than 5 seconds."""

import json
import os
import statistics
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path

from ..data.normalize import parse
from ..recorder.sink import EXT, read_lines
from ..core.types import SpotTick

NS = 1_000_000_000


def recent_spot(streams: list[str], seconds: int, root: str | None = None, stale_s: float = 5) -> list[tuple[int, float]]:
    root = Path(root or os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser()
    now = time.time()
    start = now - seconds
    ticks = []
    for name in streams:
        h = datetime.fromtimestamp(start, timezone.utc).replace(minute=0, second=0, microsecond=0)
        while h.timestamp() <= now:
            f = root / "spot" / name / f"{h:%Y-%m-%d/%H}{EXT}"
            if f.exists():
                for line in read_lines(f):
                    d = json.loads(line)
                    if d["t"] / NS < start:
                        continue
                    for ev in parse(f"spot/{name}", d["t"], d["m"]):
                        if isinstance(ev, SpotTick):
                            ticks.append((ev.ts, ev.source, ev.price))
            h += timedelta(hours=1)
    ticks.sort()
    out, last, i = [], {}, 0
    for sec in range(int(start) + 1, int(now)):
        while i < len(ticks) and ticks[i][0] <= sec * NS:
            last[ticks[i][1]] = (ticks[i][0], ticks[i][2])
            i += 1
        fresh = [p for ts, p in last.values() if sec * NS - ts <= stale_s * NS]
        if fresh:
            out.append((sec, statistics.median(fresh)))
    return out
