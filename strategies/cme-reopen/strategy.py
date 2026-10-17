"""CME reopen underdog: buy the underdog in the 15-minute window that starts at 18:00 ET on Sunday, when CME
crypto futures reopen after the weekend.

us-hours-vol's 9:30 ET bell rule (OpenUnderdog), unchanged except for the clock: weekend spot vol is 0.6-0.9x weekday,
and the Sunday 18:00 ET reopen of CME futures (closed since Friday 17:00) is a vol step. research/reopen.py (ETH, dev
data): Sunday 18:00 window vol +0.87 log vs the month mean (Sunday 17:45 +0.18, Saturday 18:00 -0.26, Monday-Wednesday
18:00 +0.2..+0.35); market log(iv/rv_fut) 0.00 vs 0.23 overall (vol underpriced); underdog +17.6c / +14.0c in halves
A / B but only 10 markets each.

  when     the window starting at Sunday 18:00 New York time
  entry    at fixed checkpoints (h = 600, 480, 360, 300, 240 s), once per market at the first one where the underdog
           is within [lo, hi] and the spread <= max_spread: buy it at the touch (+ slip_c), IOC.
  exit     hold to settlement.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from kalshi_lab.core.types import TIF, Side
from kalshi_lab.strategy import Strategy

NS = 1_000_000_000
NY = ZoneInfo("America/New_York")


def ny_dow_slot(close_ts: int) -> str:
    """'<weekday> HH:MM' New York start of the window closing at close_ts (weekday 0 = Monday, 6 = Sunday)."""
    start = datetime.fromtimestamp(close_ts / NS - 900, tz=timezone.utc).astimezone(NY)
    return f"{start.weekday()} {start.strftime('%H:%M')}"


class ReopenUnderdog(Strategy):
    params = {
        "slots": ["6 18:00"],                      # NY '<weekday> HH:MM' window starts to trade
        "checkpoints": [600, 480, 360, 300, 240],  # seconds before close; first that qualifies
        "lo": 100, "hi": 450,                      # underdog price range (mills)
        "slip_c": 0,                               # IOC this many cents through the touch (paper: 1)
        "max_spread": 60,                          # skip if ask - bid > this (mills)
    }

    def on_start(self, ctx):
        self.done: set[str] = set()

    def on_timer(self, ctx):
        for m in ctx.active_markets():
            if m.ticker in self.done:
                continue
            if ny_dow_slot(m.close_ts) not in self.p.slots:
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
            return
        mid = (book.best_bid + book.best_ask) / 2
        dog = min(mid, 1000 - mid)
        ctx.record(m.ticker, "dog_mid", dog)
        if not (self.p.lo <= dog <= self.p.hi):
            return
        if mid < 500:
            side, px = Side.BUY, min(999, book.best_ask + 10 * self.p.slip_c)
        else:
            side, px = Side.SELL, max(1, book.best_bid - 10 * self.p.slip_c)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"reopen_dog={dog:.0f}")
            self.done.add(m.ticker)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
