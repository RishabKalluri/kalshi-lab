"""Shared pricing pieces for 15-minute up/down markets.

Settlement: YES iff avg(index over the 60s before close) >= avg(index over the 60s before open).
The opening average is the market's `strike` (floor_strike). We model the index as driftless
Brownian motion in price with per-second vol `sigma` (dollars/sqrt(s)):

  * tau > 60s left: the closing average ~ N(S, sigma^2 * ((tau - 60) + 60/3))
  * tau <= 60s left: part of the average is already fixed. With `obs` = sum of the per-second
    samples already inside the window (60 - tau of them):
        avg ~ N((obs + tau * S) / 60,  sigma^2 * tau^3 / (3 * 60^2))
"""

import math
from collections import deque

WINDOW = 60


def norm_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def prob_up(spot: float, strike: float, tau: float, sigma: float, window_sum: float = 0.0,
            window_n: int = 0) -> float:
    if tau <= 0:
        return 1.0 if (window_sum / max(window_n, 1)) >= strike else 0.0
    if tau > WINDOW:
        mean = spot
        var = sigma ** 2 * ((tau - WINDOW) + WINDOW / 3)
    else:
        # Samples we haven't seen are assumed equal to `spot`: fill the gap for missing seconds.
        missing = max(0, (WINDOW - int(math.ceil(tau))) - window_n)
        mean = (window_sum + missing * spot + tau * spot) / WINDOW
        var = sigma ** 2 * tau ** 3 / (3 * WINDOW ** 2)
    sd = math.sqrt(max(var, 1e-12))
    return norm_cdf((mean - strike) / sd)


class VolEstimator:
    """EWMA of squared 1-second price changes (dollars), sampled on a 1s timer."""

    def __init__(self, halflife_s: float = 300, init_sigma: float | None = None):
        self.alpha = 1 - 0.5 ** (1 / halflife_s)
        self.var = init_sigma ** 2 if init_sigma else None
        self.last = None
        self.last_t = None

    def update(self, price: float, t_s: float):
        if self.last is not None and t_s > self.last_t:
            dt = t_s - self.last_t
            r2 = (price - self.last) ** 2 / dt
            # One update per elapsed second's worth of weight.
            a = 1 - (1 - self.alpha) ** dt
            self.var = r2 if self.var is None else (1 - a) * self.var + a * r2
        self.last, self.last_t = price, t_s

    @property
    def sigma(self) -> float | None:
        return math.sqrt(self.var) if self.var else None


class WindowAverager:
    """Per-second spot samples inside a market's final 60s, to track the partially-fixed average."""

    def __init__(self):
        self.samples: dict[int, float] = {}

    def add(self, second: int, price: float):
        self.samples.setdefault(second, price)

    def stats(self, close_s: int) -> tuple[float, int]:
        xs = [p for s, p in self.samples.items() if close_s - WINDOW <= s < close_s]
        return sum(xs), len(xs)
