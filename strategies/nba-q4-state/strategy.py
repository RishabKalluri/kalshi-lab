"""NBA late-Q4 state-model taker.

signals.csv holds, per KXNBAGAME market, the win probability of a gradient-boosted state model (trained on ESPN play-by-play
of seasons 2017-2024 only; research/model1.py) at the first play with <= 300/180/120/60 s left in Q4, usable from that play's
wallclock + 10 s. No data after the activation time is in a row. Within 30 s after activation, a taker BUY print (proves the
ask) or SELL print (proves the bid) triggers: buy YES at the ask / sell YES at the bid when the model edge after the taker
fee is >= `edge`. One entry per game and checkpoint. Prices are YES mills.
Live use needs a play-by-play poller that produces the same rows in real time (not built).
"""

import csv
import math
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


def _fee(p):  # p in 0..1
    return 0.07 * p * (1 - p)


class NbaQ4State(Strategy):
    params = {"edge": 20, "window_s": 30, "mode": 0}  # edge in mills; mode 1 = logit blend of book mid and the Monte Carlo p_mc (weights fit on Oct-Dec 2025)

    def on_start(self, ctx):
        self.sig = defaultdict(list)
        with open(Path(__file__).parent / "signals.csv") as f:
            for r in csv.DictReader(f):
                self.sig[r["ticker"]].append((int(r["act_ns"]), int(r["T"]), float(r["p_yes"]), float(r.get("p_mc") or r["p_yes"])))
        self.done = set()

    def on_trade(self, ctx, tr):
        rows = self.sig.get(tr.ticker)
        m = ctx.markets.get(tr.ticker)
        if not rows or m is None or m.result is not None:
            return
        ev = tr.ticker.rsplit("-", 1)[0]
        book = ctx.book(tr.ticker)
        if book is None or book.best_ask is None or book.best_bid is None:
            return
        for act, T, p, pmc in rows:
            if not (act <= ctx.now < act + self.p.window_s * NS) or (ev, T) in self.done:
                continue
            if self.p.mode == 1:
                mid = min(max((book.best_ask + book.best_bid) / 2000, 0.01), 0.99)
                z = 0.6376 * math.log(mid / (1 - mid)) + 0.5147 * math.log(min(max(pmc, 0.01), 0.99) / (1 - min(max(pmc, 0.01), 0.99))) + 0.2467
                p = 1 / (1 + math.exp(-z))
            if tr.taker == Side.BUY:
                ask = book.best_ask / 1000
                if (p - ask - _fee(ask)) * 1000 >= self.p.edge:
                    q = ctx.size(tr.ticker, Side.BUY, book.best_ask, prob=p, tif=TIF.IOC)
                    if q >= 1 and ctx.buy(tr.ticker, book.best_ask, q, tif=TIF.IOC, tag=f"q4s{T}") is not None:
                        self.done.add((ev, T))
            else:
                bid = book.best_bid / 1000
                if ((1 - p) - (1 - bid) - _fee(1 - bid)) * 1000 >= self.p.edge:
                    q = ctx.size(tr.ticker, Side.SELL, book.best_bid, prob=p, tif=TIF.IOC)
                    if q >= 1 and ctx.sell(tr.ticker, book.best_bid, q, tif=TIF.IOC, tag=f"q4s{T}") is not None:
                        self.done.add((ev, T))
            break
