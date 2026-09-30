"""Is passive liquidity profitable? For every recorded trade, the maker bought (taker sold) or sold
(taker bought) at the trade price. Markout = how the mid moved in the maker's favor afterwards,
at several delays and at settlement. Zero maker fees on these series, so a positive markout is edge
(before queue position: a real maker only gets some of these fills).

    uv run python scripts/markouts.py KXBTC15M [hours]
"""

import bisect
import json
import sys
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from kalshi_lab.core.book import Book
from kalshi_lab.core.types import BookDelta, BookSnapshot, FeedGap, MarketInfo, Side, Trade
from kalshi_lab.data.source import RecordedSource

series = sys.argv[1] if len(sys.argv) > 1 else "KXBTC15M"
hours = float(sys.argv[2]) if len(sys.argv) > 2 else 48
end = datetime.now(timezone.utc)
src = RecordedSource([series], end - timedelta(hours=hours), end, spot=[], warmup=timedelta(0))
DELAYS = [5, 30, 120]

books: dict[str, Book] = {}
mids: dict[str, list[tuple[int, float]]] = defaultdict(list)
trades: list[tuple[str, int, int, float, int, int]] = []  # ticker, ts, price, qty, maker_sign, spread
results: dict[str, str] = {}
closes: dict[str, int] = {}
for ev in src:
    if isinstance(ev, BookSnapshot):
        books.setdefault(ev.ticker, Book(ev.ticker)).apply_snapshot(ev)
    elif isinstance(ev, BookDelta):
        b = books.get(ev.ticker)
        if b is None:
            continue
        b.apply_delta(ev)
        if b.valid and b.mid is not None:
            mids[ev.ticker].append((ev.ts, b.mid))
    elif isinstance(ev, FeedGap):
        for b in books.values():
            b.valid = False
    elif isinstance(ev, Trade):
        b = books.get(ev.ticker)
        if b is None or not b.valid or b.best_bid is None or b.best_ask is None:
            continue
        sign = 1 if ev.taker == Side.SELL else -1  # maker bought when the taker sold
        trades.append((ev.ticker, ev.ts, ev.price, ev.qty, sign, b.best_ask - b.best_bid))
    elif isinstance(ev, MarketInfo):
        closes[ev.ticker] = ev.close_ts
        if ev.result:
            results[ev.ticker] = ev.result

agg = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))  # bucket -> delay -> [sum qty*markout, sum qty]
mid_ts = {tk: [x[0] for x in m] for tk, m in mids.items()}
for tk, ts, px, q, sign, spr in trades:
    m = mids.get(tk)
    if not m or tk not in results:
        continue
    ts_list = mid_ts[tk]
    tau = (closes[tk] - ts) / 1e9
    bucket = "0-60s" if tau < 60 else "60-300s" if tau < 300 else "300s+"
    for d in DELAYS:
        i = bisect.bisect_right(ts_list, ts + d * 10**9) - 1
        if i < 0 or m[i][0] <= ts:
            continue
        mk = sign * (m[i][1] - px)
        for b in (bucket, "all"):
            agg[b][d][0] += q * mk
            agg[b][d][1] += q
    settle = 1000 if results[tk] == "yes" else 0
    for b in (bucket, "all"):
        agg[b]["settle"][0] += q * sign * (settle - px)
        agg[b]["settle"][1] += q

print(f"{series}: {len(trades)} trades over {len(results)} settled markets (last {hours:g}h recorded)")
print("volume-weighted maker markout, in cents per contract (+ = maker wins)\n")
print(f"{'time left':>10} " + "".join(f"{f'+{d}s':>10}" for d in DELAYS) + f"{'settle':>10}{'volume':>12}")
for b in ("300s+", "60-300s", "0-60s", "all"):
    row = f"{b:>10} "
    for d in DELAYS + ["settle"]:
        s, q = agg[b][d]
        row += f"{(s / q / 10 if q else float('nan')):>10.2f}"
    row += f"{agg[b]['settle'][1]:>12,.0f}"
    print(row)
