"""Kalshi trading fees. Series with fee_type 'quadratic' charge takers
    ceil_to_cent(0.07 * contracts * P * (1 - P)),  P in dollars,
and makers nothing ('quadratic_with_maker_fees' charges makers at 0.0175). fee_multiplier scales both.
"""

import math


class Fees:
    def __init__(self, taker_rate: float = 0.07, maker_rate: float = 0.0, multiplier: float = 1.0):
        self.taker_rate = taker_rate * multiplier
        self.maker_rate = maker_rate * multiplier

    def __call__(self, price_mills: int, qty: float, maker: bool, ticker: str | None = None) -> float:
        rate = self.maker_rate if maker else self.taker_rate
        if rate == 0:
            return 0.0
        p = price_mills / 1000
        return math.ceil(round(rate * qty * p * (1 - p) * 100, 6)) / 100

    @classmethod
    def for_series(cls, series_row: dict) -> "Fees":
        mult = float(series_row.get("fee_multiplier", 1))
        maker = 0.0175 if series_row.get("fee_type") == "quadratic_with_maker_fees" else 0.0
        return cls(maker_rate=maker, multiplier=mult)


class SeriesFees:
    """Each market's fee schedule by its series (recorder/config.py MARKETS: fee_type, fee_multiplier); `default` for
    series not listed (crypto 15M: quadratic, takers only)."""

    def __init__(self, default: Fees | None = None):
        self.default = default or Fees()
        self.by_series: dict[str, Fees] = {}

    def __call__(self, price_mills: int, qty: float, maker: bool, ticker: str | None = None) -> float:
        series = ticker.split("-")[0] if ticker else ""
        f = self.by_series.get(series)
        if f is None:
            from ..recorder.config import MARKETS
            m = MARKETS.get(series)
            f = self.by_series[series] = Fees.for_series(m) if m and "fee_type" in m else self.default
        return f(price_mills, qty, maker)
