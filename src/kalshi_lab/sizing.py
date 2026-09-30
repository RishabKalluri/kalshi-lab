"""Position sizing, independent of strategy.

Strategies ask `ctx.size(ticker, side, price, prob=...)` and get a contract count back; which policy
answers is chosen per run (--sizing), so the same strategy can be tested at different risk levels.

Policies (spec string -> class):
  pct:P        risk P% of current equity per order (the default: pct:1)
  fixed:N      N contracts per order (what strategies did before this existed)
  risk:D       spend D dollars of max loss per order (qty = D / cost)
  kelly:F      fraction F of full Kelly on current equity, as a *target position* per market.
               Needs the strategy's win probability `prob`; falls back to risk sizing without one.

Cost per contract: buying YES at p risks p; selling YES at p (= buying NO at 1-p) risks 1-p.
All policies are then capped by `max_frac` of equity per market and, for taking orders, by the
displayed liquidity at or better than the limit price. RiskLimits still apply on top.
"""

from dataclasses import dataclass

from .core.types import TIF, Side


def cost_per_contract(side: Side, price: int) -> float:
    return price / 1000 if side == Side.BUY else 1 - price / 1000


@dataclass
class Sizer:
    max_frac: float = 0.05  # max fraction of equity at risk in one market

    def raw(self, ctx, ticker, side, price, prob) -> float:
        raise NotImplementedError

    def __call__(self, ctx, ticker: str, side: Side, price: int, prob: float | None = None,
                 tif: TIF = TIF.GTC) -> float:
        c = cost_per_contract(side, price)
        if c <= 0:
            return 0.0
        q = self.raw(ctx, ticker, side, price, prob)
        # Per-market exposure cap, counting what we already hold/have working in this direction.
        sign = 1 if side == Side.BUY else -1
        held = max(0.0, sign * ctx.position(ticker)) + sum(o.remaining for o in ctx.open_orders(ticker) if o.side == side)
        cap = max(0.0, self.max_frac * max(ctx.equity(), 0.0) / c - held)
        q = min(q, cap)
        if tif == TIF.IOC:  # can't take more than is displayed
            book = ctx.book(ticker)
            if book is not None:
                levels = book.asks() if side == Side.BUY else book.bids()
                avail = sum(qty for px, qty in levels if (px <= price if side == Side.BUY else px >= price))
                q = min(q, avail)
        return float(int(q))  # whole contracts


@dataclass
class Fixed(Sizer):
    contracts: float = 10

    def raw(self, ctx, ticker, side, price, prob):
        return self.contracts


@dataclass
class FixedRisk(Sizer):
    dollars: float = 25

    def raw(self, ctx, ticker, side, price, prob):
        return self.dollars / cost_per_contract(side, price)


@dataclass
class PctRisk(Sizer):
    """Risk a fixed fraction of current equity per order: scales with the account, needs no probability."""
    pct: float = 1.0

    def raw(self, ctx, ticker, side, price, prob):
        return self.pct / 100 * max(ctx.equity(), 0.0) / cost_per_contract(side, price)


@dataclass
class Kelly(Sizer):
    fraction: float = 0.25
    fallback_dollars: float = 25

    def raw(self, ctx, ticker, side, price, prob):
        c = cost_per_contract(side, price)
        if prob is None:
            return self.fallback_dollars / c
        win = prob if side == Side.BUY else 1 - prob
        f = (win - c) / (1 - c) if c < 1 else 0.0  # full Kelly fraction for a binary bet at cost c
        if f <= 0:
            return 0.0
        target = self.fraction * f * max(ctx.equity(), 0.0) / c
        sign = 1 if side == Side.BUY else -1
        held = max(0.0, sign * ctx.position(ticker))
        return max(0.0, target - held)


# Default for every mode: risk 1% of equity per order, at most 5% of equity in any one market.
# Kelly is available but needs a calibrated win probability; don't use it on an unproven edge.
DEFAULT_SIZING = "pct:1"
DEFAULT_MAX_FRAC = 0.05


def parse(spec: str | None = None, max_frac: float = DEFAULT_MAX_FRAC) -> Sizer:
    kind, _, arg = (spec or DEFAULT_SIZING).partition(":")
    if kind == "pct":
        return PctRisk(max_frac=max_frac, pct=float(arg or 1))
    if kind == "fixed":
        return Fixed(max_frac=max_frac, contracts=float(arg or 10))
    if kind == "risk":
        return FixedRisk(max_frac=max_frac, dollars=float(arg or 25))
    if kind == "kelly":
        return Kelly(max_frac=max_frac, fraction=float(arg or 0.25))
    raise ValueError(f"unknown sizing '{spec}': use pct:P, fixed:N, risk:DOLLARS or kelly:FRACTION")
