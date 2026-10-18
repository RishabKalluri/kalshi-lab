"""In-game favourite carry (taker): once per game, when a team's ask first reaches [lo, hi] after the estimated start, buy it (IOC at the ask).
Late-game favourites at 95-99c win more often than the price implies by ~1-2c net of the taker fee (research on clean NBA/NHL books and real fills);
the same carry sports-tails collects as a maker. Game start = expected_expiration - exp_lead_min (as sports-tails), no score feed needed.
Prices are YES mills.
"""

from datetime import datetime

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


def _ts(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp()) * NS


class SportsFavCarry(Strategy):
    params = {"exp_lead_min": 171, "lo": 950, "hi": 990, "start_after_min": 30}

    def on_start(self, ctx):
        self.start = {}
        self.done = set()   # event tickers already traded

    def on_timer(self, ctx):
        for m in ctx.active_markets():
            ev = m.ticker.rsplit("-", 1)[0]
            if ev in self.done:
                continue
            if m.ticker not in self.start:
                exp = (m.raw or {}).get("expected_expiration_time")
                self.start[m.ticker] = _ts(exp) - int(self.p.exp_lead_min * 60 * NS) if exp else None
            s = self.start[m.ticker]
            if s is None or ctx.now < s + int(self.p.start_after_min * 60 * NS):
                continue
            book = ctx.book(m.ticker)
            if book is None or book.best_ask is None or book.best_bid is None:
                continue
            ask = book.best_ask
            if not (self.p.lo <= ask <= self.p.hi) or ask - book.best_bid > 30:
                continue
            q = ctx.size(m.ticker, Side.BUY, ask)
            if q >= 1:
                ctx.buy(m.ticker, ask, q, tif=TIF.IOC, tag="carry")
                self.done.add(ev)
