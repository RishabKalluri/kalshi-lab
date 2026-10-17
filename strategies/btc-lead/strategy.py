"""<Strategy name>: one paragraph on what it does and why it should make money.

Prices are YES mills (0..1000; 560 = $0.56). ctx.buy = buy YES, ctx.sell = sell YES (= buy NO).
Size comes from ctx.size() (the run's sizing policy), never from the strategy.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))  # lets you import helper modules from this folder

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class MyStrategy(Strategy):
    params = {"edge": 30}  # defaults; tests can override with -p edge=40

    # Optional: if the strategy learns anything from data (a model, a threshold), fit it here.
    # The pipeline calls fit(series, until) before every walk-forward month with data before `until`
    # only, and passes the returned dict as param overrides. Write any artifacts under this folder.
    # @classmethod
    # def fit(cls, series: list[str], until: str | None) -> dict:
    #     return {"threshold": ...}

    def on_start(self, ctx):
        self.state = {}
        # Live/paper only: ctx.spot_history(series, seconds) preloads recent spot from recordings.

    def on_timer(self, ctx):
        # Called every second. Typical shape:
        for m in ctx.active_markets():
            book = ctx.book(m.ticker)
            spot = ctx.spot(series=m.series)
            if book is None or spot is None or book.best_ask is None:
                continue
            secs_left = ctx.seconds_left(m.ticker)
            # ... your signal ...
            # qty = ctx.size(m.ticker, Side.BUY, book.best_ask, tif=TIF.IOC)
            # if qty >= 1: ctx.buy(m.ticker, book.best_ask, qty, tif=TIF.IOC, tag="why")
            # ctx.record(m.ticker, "fair", my_fair_mills)   # plotted on the dashboard

    def on_settle(self, ctx, m, pnl):
        self.state.pop(m.ticker, None)
