"""US-open underdog: buy the underdog in the 15-minute window that starts at the 9:30 ET US equity open.

Crypto 15-minute vol follows the New York clock (research/seasonality.py: the intraday profile correlates 0.97
across the March DST change on NY time vs 0.75 on UTC). The biggest step of the day is the 9:30 ET window:
realized vol ~2x the 9:15 window, on BTC, ETH and SOL alike. In that window the Kalshi price's implied vol sits
~0.3 log points lower relative to the realized vol than in every other slot (research/iv_gap.py): the market
prices the rest of the window off the calm pre-open minutes and doesn't fully anticipate the opening bell. Too
little vol = the favourite is overpriced and the underdog is cheap.

  when     weekdays that are NYSE trading days, the window whose start is `slot` (09:30 New York time)
  entry    at fixed checkpoints (h = 600, 480, 360, 300, 240 s before close), once per market at the first one
           where the underdog (min(mid, 1 - mid)) is within [lo, hi]: buy it at the touch (+ slip_c), IOC.
           Skip a checkpoint when the spread is wider than max_spread (6c): paying far above the mid at the open
           lost -13.8c/contract on the 28 such fills in full test 1.
  exit     hold to settlement.
Research (development data, next real fills, after fee, first checkpoint per market): ETH +10.9c (se 4.2,
6/7 months), BTC +7.0c (se 3.9); weekends and NYSE holidays at 09:30 (placebo) -5c and -3c.
"""

import sys
from datetime import date, datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
NY = ZoneInfo("America/New_York")
# NYSE full-day closures (published years in advance; no lookahead).
NYSE_HOLIDAYS = {date.fromisoformat(x) for x in [
    "2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19",
    "2026-07-03", "2026-09-07", "2026-11-26", "2026-12-25", "2027-01-01", "2027-01-18", "2027-02-15",
    "2027-03-26", "2027-05-31", "2027-06-18", "2027-07-05", "2027-09-06", "2027-11-25", "2027-12-24"]}


def us_session_slot(close_ts: int) -> str | None:
    """'HH:MM' New York start time of the window closing at close_ts, or None on weekends / NYSE holidays."""
    start = datetime.fromtimestamp(close_ts / NS - 900, tz=timezone.utc).astimezone(NY)
    if start.weekday() >= 5 or start.date() in NYSE_HOLIDAYS:
        return None
    return start.strftime("%H:%M")


class OpenUnderdog(Strategy):
    params = {
        "slots": ["09:30"],                        # NY window starts to trade
        "checkpoints": [600, 480, 360, 300, 240],  # seconds before close; first that qualifies
        "lo": 100, "hi": 450,                      # underdog price range (mills)
        "slip_c": 0,                               # IOC this many cents through the touch (paper: 1)
        "max_spread": 60,                          # skip if ask - bid > this (mills): stale/wide quotes at the open
    }

    def on_start(self, ctx):
        self.done: set[str] = set()
        self.slot: dict[str, str | None] = {}

    def on_timer(self, ctx):
        for m in ctx.active_markets():
            if m.ticker in self.done:
                continue
            if m.ticker not in self.slot:
                self.slot[m.ticker] = us_session_slot(m.close_ts)
            if self.slot[m.ticker] not in self.p.slots:
                self.done.add(m.ticker)
                continue
            tau = int(round((m.close_ts - ctx.now) / NS))
            if tau < min(self.p.checkpoints):
                self.done.add(m.ticker)
                continue
            if tau in self.p.checkpoints:
                self._consider(ctx, m)

    def _consider(self, ctx, m):
        book = ctx.book(m.ticker)
        if book is None or book.best_bid is None or book.best_ask is None or book.best_ask < book.best_bid:
            return
        if book.best_ask - book.best_bid > self.p.max_spread:
            return  # try again at the next checkpoint
        mid = (book.best_bid + book.best_ask) / 2
        dog = min(mid, 1000 - mid)
        ctx.record(m.ticker, "dog_mid", dog)
        if not (self.p.lo <= dog <= self.p.hi):
            return
        if mid < 500:   # YES is the underdog
            side, px = Side.BUY, min(999, book.best_ask + 10 * self.p.slip_c)
        else:           # NO is the underdog: sell YES
            side, px = Side.SELL, max(1, book.best_bid - 10 * self.p.slip_c)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"open_dog={dog:.0f}")
            self.done.add(m.ticker)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.slot.pop(m.ticker, None)
