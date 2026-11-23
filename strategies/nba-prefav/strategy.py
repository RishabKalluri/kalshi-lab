"""NBA pre-game heavy favourite (taker): 12-30 h before the expected end of the game, buy the team whose ask is 90-96c.

Development screen (NBA game winners Jan-Aug 2026): taker YES prints at 90-95c in that window won ~4-5c more than priced after fee
(t=11.7, both halves); on recorded asks +2..+6c but only ~10 games a month. Trigger = a taker BUY print (it proves the ask),
IOC at the ask, one entry per game. Prices are YES mills.
"""

from datetime import datetime

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


def _ts(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()) * NS


class NbaPreFav(Strategy):
    params = {"lo": 900, "hi": 960, "min_h": 12.0, "max_h": 30.0, "max_spread": 40}

    def on_start(self, ctx):
        self.done = set()

    def on_trade(self, ctx, tr):
        m = ctx.markets.get(tr.ticker)
        ev = tr.ticker.rsplit("-", 1)[0]
        if m is None or m.result is not None or tr.taker != Side.BUY or ev in self.done:
            return
        exp = (m.raw or {}).get("expected_expiration_time")
        if not exp:
            return
        h = (_ts(exp) - ctx.now) / NS / 3600
        if not (self.p.min_h <= h <= self.p.max_h):
            return
        book = ctx.book(tr.ticker)
        if book is None or book.best_ask is None or book.best_bid is None:
            return
        ask = book.best_ask
        if not (self.p.lo <= ask <= self.p.hi) or ask - book.best_bid > self.p.max_spread:
            return
        q = ctx.size(tr.ticker, Side.BUY, ask, tif=TIF.IOC)
        if q >= 1 and ctx.buy(tr.ticker, ask, q, tif=TIF.IOC, tag="fav") is not None:
            self.done.add(ev)
