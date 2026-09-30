"""Copy this file to start a new strategy.

    uv run kalshi-lab backtest strategies/my_strat.py --source recorded --hours 6
    uv run kalshi-lab paper    strategies/my_strat.py
    uv run kalshi-lab live     strategies/my_strat.py --confirm

Prices are YES mills (0..1000; 560 = $0.56). ctx.buy = buy YES, ctx.sell = sell YES (= buy NO).
"""

from kalshi_lab.core.types import TIF, Side
from kalshi_lab.strategy import Strategy

NS = 1_000_000_000


class MyStrategy(Strategy):
    params = {"edge": 30}  # override with -p edge=40, sweep with --sweep edge=20,30,40

    def on_start(self, ctx):
        self.state = {}

    def on_market(self, ctx, m):
        # m.ticker, m.strike (opening 60s BRTI average), m.open_ts, m.close_ts
        pass

    def on_timer(self, ctx):
        # Called every --timer-ms (default 1s). Most strategies live here.
        spot = ctx.spot()  # median of this series' fresh spot feeds; ctx.spot(series=m.series) if trading several
        for m in ctx.active_markets():
            book = ctx.book(m.ticker)  # None until the book is valid
            if book is None or spot is None:
                continue
            secs_left = ctx.seconds_left(m.ticker)
            pos = ctx.position(m.ticker)
            # book.best_bid, book.best_ask, book.bids(), book.asks(), ctx.open_orders(m.ticker)
            # Size comes from the run's sizing policy (--sizing fixed:N | risk:$ | kelly:F), not the strategy:
            # qty = ctx.size(m.ticker, Side.BUY, book.best_ask, prob=my_p_yes, tif=TIF.IOC)
            # if qty >= 1: ctx.buy(m.ticker, book.best_ask, qty, tif=TIF.IOC)

    def on_fill(self, ctx, f):
        # f.side, f.price, f.qty, f.fee, f.maker
        pass

    def on_settle(self, ctx, m, pnl):
        # m.result is 'yes' or 'no'; pnl includes fees and payout for this market
        pass
