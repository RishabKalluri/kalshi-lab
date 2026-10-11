"""Top-of-hour calm: buy the favourite in the 15-minute window that closes on the hour (starts at :45).

Crypto vol has a minute-of-hour cycle (research/minute_vol.py, Binance 1 s, dev data): every quarter-hour starts
with a burst and decays, and the last quarter of the hour (:45 -> :00) is the calmest, 0.85-0.90x the hour's mean
variance vs 1.10x for :00 -> :15, on BTC, ETH and SOL in both halves. Kalshi prices all four quarter-hour windows off
the same trailing vol, so in the :45 window it overprices the remaining move: the favourite is too cheap
(research/fav_by_quarter.py: favourite at the next real fill after fee, one trade per market, :45 windows ETH
+1.1/+0.4c, SOL +1.1/-0.1c, BTC +1.4/+2.4c in Dec-Apr / May-Aug; -1..-5c in :00/:15 windows).

  when     windows whose start minute is in `minutes` (default :45), every day, all configured series
  entry    at h = 720 s before close (3 minutes in), once per market, if the favourite's mid is within [lo, hi] (650-900 mills: a binary's vol sensitivity is zero at 50c and peaks
           near 84c, and the taker fee is highest at 50c): buy the favourite at the touch (+ slip_c), IOC.
  exit     hold to settlement.
v2: only h=720. Full test 1 (h 720/600/480/360) made +2.2c/ct on the h=720 entries and ~0/-1.8c on the later
fallbacks: at 720 the market's trailing vol still contains the burst that opens every quarter-hour, so it overstates
the calm remainder most; later, trailing vol has caught up.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class HourCalmFavourite(Strategy):
    params = {
        "minutes": [45],                     # window start minutes (UTC minute of hour) to trade
        "checkpoints": [720],                # seconds before close (v1 also tried 600/480/360: ~0 or negative)
        "lo": 650, "hi": 900,                # favourite mid range (mills)
        "slip_c": 0,                         # IOC this many cents through the touch (paper: 1)
    }

    def on_start(self, ctx):
        self.done: set[str] = set()

    def on_timer(self, ctx):
        for m in ctx.active_markets():
            if m.ticker in self.done:
                continue
            start_min = ((m.close_ts // NS - 900) // 60) % 60
            if start_min not in self.p.minutes:
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
        mid = (book.best_bid + book.best_ask) / 2
        fav = max(mid, 1000 - mid)
        ctx.record(m.ticker, "fav_mid", fav)
        if not (self.p.lo <= fav <= self.p.hi):
            return
        if mid >= 500:  # YES is the favourite
            side, px = Side.BUY, min(999, book.best_ask + 10 * self.p.slip_c)
        else:           # NO is the favourite: sell YES
            side, px = Side.SELL, max(1, book.best_bid - 10 * self.p.slip_c)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"fav={fav:.0f}")
            self.done.add(m.ticker)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
