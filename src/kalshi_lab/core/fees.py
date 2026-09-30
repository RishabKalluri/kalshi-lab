"""Kalshi trading fees. Series with fee_type 'quadratic' charge takers
    ceil_to_cent(0.07 * contracts * P * (1 - P)),  P in dollars,
and makers nothing ('quadratic_with_maker_fees' charges makers at 0.0175). fee_multiplier scales both.
"""

import math


class Fees:
    def __init__(self, taker_rate: float = 0.07, maker_rate: float = 0.0, multiplier: float = 1.0):
        self.taker_rate = taker_rate * multiplier
        self.maker_rate = maker_rate * multiplier

    def __call__(self, price_mills: int, qty: float, maker: bool) -> float:
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
