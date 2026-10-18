"""Mention sell-YES: on "What will Trump say during <event>" word markets, hit the YES bid shortly after the market starts trading.

Retail buys the headline-word YES lottery ticket; only ~36% of words are said but opening prices are ~50c (strategies/mention-no screen: sell YES at the
proven bid nets +6.5c, t~1.7, 133 markets). A taker SELL trade proves the bid, so the rule triggers on one: if the bid is in [lo, hi] and the market's first
trade was at most `max_age_h` hours ago, buy NO at the bid (IOC), once per market, held to settlement.
Prices are YES mills; ctx.sell(YES) = buy NO.
"""

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class MentionSell(Strategy):
    params = {
        "lo": 100,
        "hi": 900,
        "max_age_h": 1.0,    # hours since the market's first trade
        "max_spread": 300,
    }

    def on_start(self, ctx):
        self.first = {}
        self.done = set()

    def on_trade(self, ctx, tr):
        t = tr.ticker
        self.first.setdefault(t, ctx.now)
        if t in self.done or tr.taker != Side.SELL:
            return
        m = ctx.markets.get(t)
        if m is None or m.result is not None:
            return
        if (ctx.now - self.first[t]) / NS / 3600 > self.p.max_age_h:
            return
        book = ctx.book(t)
        if book is None or book.best_bid is None or book.best_ask is None:
            return
        bid, ask = book.best_bid, book.best_ask
        if not (self.p.lo <= bid <= self.p.hi) or ask - bid > self.p.max_spread:
            return
        qty = ctx.size(t, Side.SELL, bid, tif=TIF.IOC)
        if qty < 1:
            return
        if ctx.sell(t, bid, qty, tif=TIF.IOC, tag="no") is not None:
            self.done.add(t)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
        self.first.pop(m.ticker, None)
