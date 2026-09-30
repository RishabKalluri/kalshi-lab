"""Normalized event and order types shared by backtest, paper and live.

Conventions
-----------
* Prices are integer mills of a dollar: 0..1000 (Kalshi's finest tick is $0.001). 560 == $0.56.
* Everything is quoted in YES terms. Buying NO at 0.44 is the same as selling YES at 0.56;
  a negative YES position is a long NO position.
* Quantities are float contracts (Kalshi allows fractional contracts).
* Timestamps are int nanoseconds since epoch (local receive time for recorded data).
"""

from dataclasses import dataclass, field
from enum import Enum


def to_mills(dollars: str | float) -> int:
    return round(float(dollars) * 1000)


class Side(str, Enum):
    BUY = "buy"   # buy YES  (== sell NO)
    SELL = "sell"  # sell YES (== buy NO)


class TIF(str, Enum):
    GTC = "gtc"    # rest until filled/cancelled
    IOC = "ioc"    # take what's available, cancel the rest
    POST = "post"  # post-only GTC: rejected if it would cross the book on arrival (never pays taker fees)


@dataclass(slots=True)
class Event:
    ts: int


@dataclass(slots=True)
class MarketInfo(Event):
    """Market metadata. `result` is set ('yes'/'no') once settled."""
    ticker: str
    series: str
    open_ts: int
    close_ts: int
    strike: float | None  # floor_strike: for up/down markets, the opening reference price
    result: str | None = None
    settle_value: float | None = None
    raw: dict = field(default_factory=dict, repr=False)


@dataclass(slots=True)
class BookSnapshot(Event):
    ticker: str
    yes_bids: dict[int, float]  # price -> qty
    no_bids: dict[int, float]


@dataclass(slots=True)
class BookDelta(Event):
    ticker: str
    side: str  # 'yes' or 'no' (which bid ladder)
    price: int
    delta: float


@dataclass(slots=True)
class Trade(Event):
    ticker: str
    price: int  # YES price
    qty: float
    taker: Side  # BUY = taker bought YES (lifted the ask), SELL = taker sold YES (hit the bid)


@dataclass(slots=True)
class SpotTick(Event):
    source: str  # e.g. 'coinbase_btcusd'
    price: float
    bid: float | None = None
    ask: float | None = None


@dataclass(slots=True)
class FeedGap(Event):
    """Recorder disconnected/reconnected: book state for `stream` is unreliable until the next snapshot."""
    stream: str


@dataclass(slots=True)
class Timer(Event):
    pass


@dataclass(slots=True)
class Order:
    id: int
    ticker: str
    side: Side
    price: int
    qty: float
    tif: TIF
    submit_ts: int
    tag: str = ""
    filled: float = 0.0
    status: str = "pending"  # pending -> open -> filled | cancelled | rejected
    queue_ahead: float = 0.0
    xid: str = ""  # exchange order id (live only)

    @property
    def remaining(self) -> float:
        return self.qty - self.filled

    @property
    def is_live(self) -> bool:
        return self.status in ("pending", "open")


@dataclass(slots=True)
class Fill(Event):
    order_id: int
    ticker: str
    side: Side
    price: int
    qty: float
    fee: float  # dollars
    maker: bool
    tag: str = ""


# Kalshi "tapered_deci_cent": $0.001 ticks below $0.10 and above $0.90, $0.01 in between.
DEFAULT_PRICE_RANGES = [(0, 100, 1), (100, 900, 10), (900, 1000, 1)]


def price_ranges(raw_market: dict) -> list[tuple[int, int, int]]:
    rs = raw_market.get("price_ranges")
    if not rs:
        return DEFAULT_PRICE_RANGES
    return [(to_mills(r["start"]), to_mills(r["end"]), to_mills(r["step"])) for r in rs]


def snap_price(price: int, side: "Side", ranges=DEFAULT_PRICE_RANGES) -> int:
    """Round to a valid tick, never in the direction that costs more (buys down, sells up)."""
    for lo, hi, step in ranges:
        if lo <= price <= hi:
            off = (price - lo) % step
            if off == 0:
                return price
            return price - off if side == Side.BUY else price - off + step
    return price
