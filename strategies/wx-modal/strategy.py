"""Weather modal bracket taker: 24-36 h before the close, buy YES on the event's highest-priced bracket at the ask.

KXHIGH ladders are wide early (implied variance ~1.4x realised, wx-fav-bid): the most likely bracket wins slightly more often than its
price. Dev screen (10 cities, ~2,600 city-days, last-trade ask, fee included): +0.4..+1.7c per contract at 24/30/36 h, day-clustered
se ~1c. v1 buys once per event, on a taker-buy trade (proves the ask), when this market's last price is the event's highest.
Prices are YES mills.
"""

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402


class WxModal(Strategy):
    params = {
        "min_ttc_h": 24.0,
        "max_ttc_h": 36.0,
        "lo": 150,          # ask range, mills
        "hi": 850,
        "min_known": 3,     # brackets of the event with a known last price
    }

    def on_start(self, ctx):
        self.last = {}
        self.done = set()

    def on_trade(self, ctx, tr):
        t = tr.ticker
        self.last[t] = tr.price
        if tr.taker != Side.BUY:
            return
        m = ctx.markets.get(t)
        if m is None or m.result is not None:
            return
        ev = t.rsplit("-", 1)[0]
        if ev in self.done:
            return
        h = ctx.seconds_left(t) / 3600
        if h > self.p.max_ttc_h or h < self.p.min_ttc_h:
            return
        sib = [p for k, p in self.last.items() if k.rsplit("-", 1)[0] == ev]
        if len(sib) < self.p.min_known or tr.price < max(sib):
            return
        book = ctx.book(t)
        if book is None or book.best_ask is None:
            return
        ask = book.best_ask
        if not (self.p.lo <= ask <= self.p.hi):
            return
        qty = ctx.size(t, Side.BUY, ask, tif=TIF.IOC)
        if qty < 1:
            return
        if ctx.buy(t, ask, qty, tif=TIF.IOC, tag="modal") is not None:
            self.done.add(ev)

    def on_settle(self, ctx, m, pnl):
        self.last.pop(m.ticker, None)
