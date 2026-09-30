"""Strategy interface. The same class runs in backtest, paper and live; only the exchange behind
`ctx` changes.

    class MyStrategy(Strategy):
        params = {"edge": 30, "size": 5}          # defaults, overridable from the CLI with -p edge=40

        def on_timer(self, ctx):
            for m in ctx.active_markets():
                book = ctx.book(m.ticker)
                ...
                ctx.buy(m.ticker, price=520, qty=self.p.size, tif=TIF.IOC)

Prices are YES mills (0..1000), see core/types.py.
"""

import logging
import statistics
from types import SimpleNamespace

from .core.book import Book
from .core.portfolio import Portfolio
from .core.risk import RiskLimits
from .core.types import (DEFAULT_PRICE_RANGES, TIF, Fill, MarketInfo, Order, Side, SpotTick, Trade, price_ranges,
                         snap_price)

NS = 1_000_000_000


class Strategy:
    params: dict = {}

    def __init__(self, **overrides):
        unknown = set(overrides) - set(self.params)
        if unknown:
            raise ValueError(f"unknown params for {type(self).__name__}: {sorted(unknown)}")
        self.p = SimpleNamespace(**{**self.params, **overrides})

    # Optional, for strategies with a trained model: the validation pipeline calls
    #     @classmethod
    #     def fit(cls, series: list[str], until: str | None) -> dict:   # -> param overrides
    # before each walk-forward month with `until` = that month's start, so the model only ever sees the past.

    # All hooks are optional.
    def on_start(self, ctx: "Context"): ...
    def on_market(self, ctx: "Context", m: MarketInfo): ...          # a market was listed
    def on_book(self, ctx: "Context", ticker: str, book: Book): ...  # top of book changed
    def on_trade(self, ctx: "Context", t: Trade): ...
    def on_spot(self, ctx: "Context", t: SpotTick): ...
    def on_timer(self, ctx: "Context"): ...                          # every `timer_ms` of event time
    def on_fill(self, ctx: "Context", f: Fill): ...
    def on_settle(self, ctx: "Context", m: MarketInfo, pnl: float): ...
    def on_end(self, ctx: "Context"): ...


class Context:
    def __init__(self, exchange, risk: RiskLimits, portfolio: Portfolio, spot_stale_s: float = 5,
                 spot_map: dict[str, list[str]] | None = None, sizer=None):
        self.exchange = exchange
        self.risk = risk
        self.portfolio = portfolio
        self.now = 0
        self.books: dict[str, Book] = {}
        self.markets: dict[str, MarketInfo] = {}
        self.orders: dict[int, Order] = {}
        self._spot: dict[str, tuple[int, float]] = {}
        self._spot_stale_ns = int(spot_stale_s * NS)
        self.spot_map = spot_map or {}  # series -> spot sources that track its index
        self._next_id = 1
        self.halted = False
        self.log = logging.getLogger("strategy")
        self.rejects: list[tuple[int, Order, str]] = []
        self.recorded: dict[str, dict[str, float]] = {}  # ticker -> name -> latest value
        # Live/paper only: spot_history(series, seconds) -> [(unix_sec, composite price)] from recorded files.
        self.spot_history = None
        from .sizing import parse
        self.sizer = sizer or parse()

    def size(self, ticker: str, side: Side, price: int, prob: float | None = None, tif: TIF = TIF.GTC) -> float:
        """Contracts to trade, from the run's sizing policy (--sizing). `prob` = your P(YES), if you have one."""
        return self.sizer(self, ticker, Side(side), int(price), prob, TIF(tif))

    def equity(self) -> float:
        """Cash plus open positions marked at mid."""
        marks = {t: b.mid for t, b in self.books.items() if b.valid and b.mid is not None}
        return self.portfolio.equity(marks)

    def record(self, ticker: str, name: str, value: float):
        """Attach a value (e.g. your fair price, in mills) to a market's timeline for the dashboard."""
        self.recorded.setdefault(ticker, {})[name] = value

    # --- market data -----------------------------------------------------
    def active_markets(self, series: str | None = None) -> list[MarketInfo]:
        return [m for m in self.markets.values()
                if m.open_ts <= self.now < m.close_ts and m.result is None and (series is None or m.series == series)]

    def book(self, ticker: str) -> Book | None:
        b = self.books.get(ticker)
        return b if b is not None and b.valid else None

    def spot(self, series: str | None = None, source: str | None = None) -> float | None:
        """Composite underlying price for `series`: median of its fresh spot sources.

        `series` may be omitted when only one series is loaded. `source` returns one feed's last price.
        """
        if source:
            v = self._spot.get(source)
            return v[1] if v else None
        if series is None:
            if len(self.spot_map) != 1:
                raise ValueError(f"ctx.spot(): pass series=, loaded series are {list(self.spot_map)}")
            series = next(iter(self.spot_map))
        fresh = [v[1] for src in self.spot_map.get(series, ())
                 if (v := self._spot.get(src)) and self.now - v[0] <= self._spot_stale_ns]
        return statistics.median(fresh) if fresh else None

    def seconds_left(self, ticker: str) -> float:
        return (self.markets[ticker].close_ts - self.now) / NS

    # --- account ---------------------------------------------------------
    def position(self, ticker: str) -> float:
        return self.portfolio.pos.get(ticker, 0.0)

    def open_orders(self, ticker: str | None = None) -> list[Order]:
        return [o for o in self.orders.values() if o.is_live and (ticker is None or o.ticker == ticker)]

    @property
    def cash(self) -> float:
        return self.portfolio.cash

    # --- trading ---------------------------------------------------------
    def buy(self, ticker: str, price: int, qty: float, tif: TIF = TIF.GTC, tag: str = "") -> Order | None:
        return self._order(ticker, Side.BUY, price, qty, tif, tag)

    def sell(self, ticker: str, price: int, qty: float, tif: TIF = TIF.GTC, tag: str = "") -> Order | None:
        return self._order(ticker, Side.SELL, price, qty, tif, tag)

    def _order(self, ticker, side, price, qty, tif, tag) -> Order | None:
        m = self.markets.get(ticker)
        price = snap_price(int(price), side, price_ranges(m.raw) if m else DEFAULT_PRICE_RANGES)
        o = Order(self._next_id, ticker, side, price, round(float(qty), 2), TIF(tif), self.now, tag)
        self._next_id += 1
        reason = "risk halt" if self.halted else self.risk.check(o, self.position(ticker), self.open_orders(ticker))
        if reason:
            o.status = "rejected"
            self.rejects.append((self.now, o, reason))
            if len(self.rejects) <= 5:
                self.log.warning("order rejected by risk limits: %s (%s %s %s@%s)", reason, ticker, side.value, qty, price)
            return None
        self.orders[o.id] = o
        self.exchange.submit(o, self.now)
        return o

    def cancel(self, order: Order | int):
        o = self.orders[order] if isinstance(order, int) else order
        if o.is_live:
            self.exchange.cancel(o, self.now)

    def cancel_all(self, ticker: str | None = None):
        for o in self.open_orders(ticker):
            self.cancel(o)
