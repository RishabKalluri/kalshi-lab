"""Integrity check: replay recorded order books and compare our top of book with the
yes_bid/yes_ask Kalshi reports on its `ticker` channel."""

import json
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone

from kalshi_lab.core.book import Book
from kalshi_lab.core.types import BookDelta, BookSnapshot, to_mills
from kalshi_lab.data.normalize import parse
from kalshi_lab.data.source import _hours, _root
from kalshi_lab.recorder.sink import EXT, read_lines

series = sys.argv[1] if len(sys.argv) > 1 else "KXBTC15M"
hours = float(sys.argv[2]) if len(sys.argv) > 2 else 1
end = datetime.now(timezone.utc)
start = end - timedelta(hours=hours)
root = _root(None)
books: dict[str, Book] = {}
res = Counter()
pending = []
hist: dict[str, list] = {}
for h in _hours(start, end):
    f = root / f"kalshi_ws/{series}" / f"{h}{EXT}"
    if not f.exists():
        continue
    for line in read_lines(f):
        d = json.loads(line)
        m = d["m"]
        if m.get("type") == "ticker":
            b = books.get(m["msg"]["market_ticker"])
            if b is None or not b.valid:
                continue
            ours = (b.best_bid or 0, b.best_ask or 1000)
            theirs = (to_mills(m["msg"]["yes_bid_dollars"]), to_mills(m["msg"]["yes_ask_dollars"]) or 1000)
            # The ticker channel is published independently of deltas, so allow a short lag either way.
            pending.append((d["t"], b.ticker, theirs))
            continue
            continue
        for e in parse(f"kalshi_ws/{series}", d["t"], m):
            if isinstance(e, BookSnapshot):
                books.setdefault(e.ticker, Book(e.ticker)).apply_snapshot(e)
            elif isinstance(e, BookDelta) and e.ticker in books:
                books[e.ticker].apply_delta(e)
            else:
                continue
            b = books[e.ticker]
            hist.setdefault(e.ticker, []).append((d["t"], (b.best_bid or 0, b.best_ask or 1000)))
import bisect

for t, tk, theirs in pending:
    h = hist[tk]
    ts = [x[0] for x in h]
    i = bisect.bisect_right(ts, t) - 1
    lo, hi = bisect.bisect_left(ts, t - 500_000_000), bisect.bisect_right(ts, t + 500_000_000)
    if i >= 0 and h[i][1] == theirs:
        res["exact"] += 1
    elif any(h[j][1] == theirs for j in range(lo, hi)):
        res["within_500ms"] += 1
    else:
        res["mismatch"] += 1
ok = res["exact"] + res["within_500ms"]
print(series, dict(res), f"{ok / max(1, sum(res.values())):.1%} consistent")
