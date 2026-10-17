"""Scheduled-bell underdog: one rule over the two TradFi-driven vol steps Kalshi 15-minute crypto prices too late.

us-hours-vol found the 9:30 ET equity open (NYSE trading days) is the biggest scheduled vol step of the day and that
Kalshi's implied vol under-reacts in that window (underdog cheap). cme-reopen found the same at the Sunday 18:00 ET CME
futures reopen. Each alone is ~1 market per coin per day / week, too few to prove; pooled they are one rule.

  when     the window starting at 09:30 ET on NYSE trading days, or at 18:00 ET on Sunday (`bells`)
  entry    at fixed checkpoints (h = 600, 480, 360, 300, 240 s before close), once per market at the first one where
           the underdog (min(mid, 1 - mid)) is within [lo, hi] and the spread <= max_spread: buy it at the touch
           (+ slip_c), IOC.
  exit     hold to settlement.
Rule and parameters are us-hours-vol v2's, unchanged; the only addition is the Sunday bell.
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


def bell_slot(close_ts: int) -> str | None:
    """'us_open' for the 09:30 ET window on a NYSE trading day, 'cme_reopen' for Sunday 18:00 ET, else the
    'HH:MM' New York start (for smoke-test overrides) prefixed with the weekday number, e.g. '2 14:00'."""
    start = datetime.fromtimestamp(close_ts / NS - 900, tz=timezone.utc).astimezone(NY)
    hm, dow = start.strftime("%H:%M"), start.weekday()
    if hm == "09:30" and dow < 5 and start.date() not in NYSE_HOLIDAYS:
        return "us_open"
    if hm == "18:00" and dow == 6:
        return "cme_reopen"
    return f"{dow} {hm}"


class BellUnderdog(Strategy):
    params = {
        "bells": ["us_open", "cme_reopen"],        # windows to trade
        "checkpoints": [600, 480, 360, 300, 240],  # seconds before close; first that qualifies
        "lo": 100, "hi": 450,                      # underdog price range (mills)
        "slip_c": 0,                               # IOC this many cents through the touch (paper: 1)
        "max_spread": 60,                          # skip if ask - bid > this (mills): stale/wide quotes at the open
    }

    def on_start(self, ctx):
        self.done: set[str] = set()
        self.slot: dict[str, str] = {}

    def on_timer(self, ctx):
        for m in ctx.active_markets():
            if m.ticker in self.done:
                continue
            if m.ticker not in self.slot:
                self.slot[m.ticker] = bell_slot(m.close_ts)
            if self.slot[m.ticker] not in self.p.bells:
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
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"bell_dog={dog:.0f}")
            self.done.add(m.ticker)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.slot.pop(m.ticker, None)
