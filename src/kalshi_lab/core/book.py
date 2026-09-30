"""Kalshi order book in YES terms.

Kalshi publishes two bid ladders: YES bids and NO bids. A NO bid at p is a YES ask at 1000 - p.
"""

from .types import BookDelta, BookSnapshot


class Book:
    __slots__ = ("ticker", "yes_bids", "no_bids", "valid")

    def __init__(self, ticker: str):
        self.ticker = ticker
        self.yes_bids: dict[int, float] = {}
        self.no_bids: dict[int, float] = {}
        self.valid = False

    def apply_snapshot(self, s: BookSnapshot):
        self.yes_bids = dict(s.yes_bids)
        self.no_bids = dict(s.no_bids)
        self.valid = True

    def apply_delta(self, d: BookDelta):
        ladder = self.yes_bids if d.side == "yes" else self.no_bids
        q = ladder.get(d.price, 0.0) + d.delta
        if q > 1e-9:
            ladder[d.price] = q
        else:
            ladder.pop(d.price, None)

    # --- YES-terms views -------------------------------------------------
    @property
    def best_bid(self) -> int | None:
        return max(self.yes_bids) if self.yes_bids else None

    @property
    def best_ask(self) -> int | None:
        return 1000 - max(self.no_bids) if self.no_bids else None

    @property
    def mid(self) -> float | None:
        b, a = self.best_bid, self.best_ask
        if b is None or a is None:
            return None
        return (b + a) / 2

    def bid_qty(self, price: int) -> float:
        return self.yes_bids.get(price, 0.0)

    def ask_qty(self, price: int) -> float:
        return self.no_bids.get(1000 - price, 0.0)

    def asks(self) -> list[tuple[int, float]]:
        """YES asks, best (lowest) first."""
        return sorted(((1000 - p, q) for p, q in self.no_bids.items()))

    def bids(self) -> list[tuple[int, float]]:
        """YES bids, best (highest) first."""
        return sorted(self.yes_bids.items(), reverse=True)

    def __repr__(self):
        return f"Book({self.ticker} {self.best_bid}/{self.best_ask})"
