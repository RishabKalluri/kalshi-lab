"""XRP tie-goes-YES: in the last minute of a KXXRP15M window, buy YES at the ask.

The rule is "the 60 s average at the close is AT LEAST the 60 s average at the open", and XRP's strike and expiration value are rounded to 4 decimals
(about $1-3 per XRP, i.e. 1 tick ~ 0.3-1 bp), so exact ties are common once the final average is nearly known, and a tie resolves YES. ETH/SOL/BTC/DOGE settle at
2-6+ decimals, where ties are rare. The market prices the last minute like a continuous distribution, so YES is underpriced and NO overpriced:
development takers in the last minute earned YES +10..+14c at 10-60c (both halves), NO -16..-24c (200 days).
Rule: in the last `max_s` seconds, on a taker BUY trade (it proves the ask), if the ask is in [lo, hi] buy YES (IOC), once per market, held to settlement.
Prices are YES mills.
"""

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402


class XrpTie(Strategy):
    params = {
        "max_s": 30.0,      # only in the last seconds before the close
        "min_s": 3.0,       # not inside the last few seconds (order latency)
        "lo": 100,          # ask range, mills
        "hi": 700,
        "max_spread": 300,
    }

    def on_start(self, ctx):
        self.done = set()

    def on_trade(self, ctx, tr):
        t = tr.ticker
        if t in self.done or tr.taker != Side.BUY:
            return
        m = ctx.markets.get(t)
        if m is None or m.result is not None:
            return
        s = ctx.seconds_left(t)
        if s > self.p.max_s or s < self.p.min_s:
            return
        book = ctx.book(t)
        if book is None or book.best_bid is None or book.best_ask is None:
            return
        bid, ask = book.best_bid, book.best_ask
        if not (self.p.lo <= ask <= self.p.hi) or ask - bid > self.p.max_spread:
            return
        qty = ctx.size(t, Side.BUY, ask, tif=TIF.IOC)
        if qty < 1:
            return
        if ctx.buy(t, ask, qty, tif=TIF.IOC, tag="tie") is not None:
            self.done.add(t)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
