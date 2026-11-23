"""Hour-end late favourite: buy the 85-98c favourite in the last 1-4 minutes of the 15-minute window that closes on
the hour (:00 UTC), nothing in the other three quarter-hour windows.

Dev screen (hour-pin/research/hourpin.py, 5 coins, Dec-Aug): the last five minutes before an hour close are ~15%
calmer than the same minutes of a window that opens on the hour (all five coins, both halves of the year) and the
market's implied vol only prices part of that, so favourites in the hour-closing window win more often than their
price says (+0.74c/contract at next fills after fees; windows closing at :15 lose 1.6c). One entry per market at the
first checkpoint where the favourite's ask is in the band. Hold to settlement.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class HourPin(Strategy):
    params = {
        "checkpoints": [240, 180, 120, 60],  # seconds before close; one entry per market at the first that fires
        "lo": 850, "hi": 980,                # favourite price band (mills)
        "close_minute": 0,                   # trade only windows closing at this minute of the hour (UTC)
        "slip_c": 0,                         # IOC this many cents through the touch (paper: 1)
    }

    def on_start(self, ctx):
        self.done: set[str] = set()

    def on_timer(self, ctx):
        for m in ctx.active_markets():
            if m.ticker in self.done:
                continue
            tau = int(round((m.close_ts - ctx.now) / NS))
            if tau < min(self.p.checkpoints):
                self.done.add(m.ticker)
                continue
            if tau not in self.p.checkpoints:
                continue
            if (m.close_ts // NS // 60) % 60 != self.p.close_minute:
                self.done.add(m.ticker)
                continue
            self._consider(ctx, m)

    def _consider(self, ctx, m):
        book = ctx.book(m.ticker)
        if book is None or book.best_bid is None or book.best_ask is None or book.best_ask < book.best_bid:
            return
        yes_fav = (book.best_bid + book.best_ask) >= 1000
        price = book.best_ask if yes_fav else 1000 - book.best_bid
        if not (self.p.lo <= price <= self.p.hi):
            return
        if yes_fav:
            side, px = Side.BUY, min(999, book.best_ask + 10 * self.p.slip_c)
        else:
            side, px = Side.SELL, max(1, book.best_bid - 10 * self.p.slip_c)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"fav@{price}")
            self.done.add(m.ticker)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
