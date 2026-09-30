from collections import defaultdict

from .types import Fill, Side


class Portfolio:
    """Cash and net YES positions. Settlement pays $1 per YES contract if the market resolves yes."""

    def __init__(self, cash: float = 0.0):
        self.start_cash = cash
        self.cash = cash
        self.pos: dict[str, float] = defaultdict(float)
        self.fees = 0.0
        self.by_market: dict[str, dict] = defaultdict(lambda: {"cash": 0.0, "fees": 0.0, "volume": 0.0, "fills": 0,
                                                               "maker_qty": 0.0, "taker_qty": 0.0})

    def apply(self, f: Fill):
        sign = 1 if f.side == Side.BUY else -1
        flow = -sign * f.qty * f.price / 1000 - f.fee
        self.cash += flow
        self.fees += f.fee
        self.pos[f.ticker] += sign * f.qty
        m = self.by_market[f.ticker]
        m["cash"] += flow
        m["fees"] += f.fee
        m["volume"] += f.qty
        m["fills"] += 1
        m["maker_qty" if f.maker else "taker_qty"] += f.qty

    def settle(self, ticker: str, result: str) -> float:
        """Returns the market's total PnL (trading cash flows + payout)."""
        q = self.pos.pop(ticker, 0.0)
        payout = q if result == "yes" else 0.0
        self.cash += payout
        m = self.by_market[ticker]
        m["payout"] = payout
        m["final_pos"] = q
        m["result"] = result
        m["pnl"] = m["cash"] + payout
        return m["pnl"]

    def equity(self, marks: dict[str, float]) -> float:
        """Cash plus open positions marked at `marks` (YES price in mills)."""
        return self.cash + sum(q * marks.get(t, 500) / 1000 for t, q in self.pos.items())
