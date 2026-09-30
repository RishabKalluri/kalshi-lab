from dataclasses import dataclass

from .types import Order, Side


@dataclass
class RiskLimits:
    """Checked on every order in every mode, so what you backtest is what can run live."""
    max_order_qty: float = 100
    max_position: float = 500      # abs net YES contracts per market, counting open orders
    max_open_orders: int = 20      # per market
    max_loss: float | None = None  # stop trading (cancel + reject) once realized+marked loss exceeds this ($)
    min_price: int = 1
    max_price: int = 999

    def check(self, o: Order, position: float, open_orders: list[Order]) -> str | None:
        if o.qty <= 0 or o.qty > self.max_order_qty:
            return f"qty {o.qty} outside (0, {self.max_order_qty}]"
        if not (self.min_price <= o.price <= self.max_price):
            return f"price {o.price} outside [{self.min_price}, {self.max_price}]"
        if len(open_orders) >= self.max_open_orders:
            return "too many open orders"
        sign = 1 if o.side == Side.BUY else -1
        worst = position + sign * o.qty + sum((1 if x.side == o.side else 0) * sign * x.remaining for x in open_orders)
        if abs(worst) > self.max_position:
            return f"would exceed max_position {self.max_position}"
        return None
