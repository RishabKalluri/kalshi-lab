"""Settlement-average lock-in taker: price the 60 s settlement average from Binance 1 s data, buy where Kalshi's ask is cheap.

The market settles on the simple average of the CF index over the last 60 seconds before close versus the
average over the 60 s before open (the strike). In the last 45 s part of that average is already fixed, so
P(YES) = Phi((E[avg] - K) / sd), with E[avg] = (sum of known seconds + remaining * last price) / 60 + basis and
sd from the random-walk variance of the unknown seconds (sigma^2 * n(n+1)(2n+1)/6 / 60^2) plus a basis-change
noise term (measured: Binance 60 s average + open basis tracks the CF average to ~1.7 bp). Research on trade
prints (dev data, 5 coins): when this probability exceeds the printed ask of a 60-98c favourite by >= 3c, the
buyer earned +2..+6c/contract per market. Entries: IOC at the touch, once per market, in the last 45 s.
"""

import math
import sys
from collections import deque
from pathlib import Path
from statistics import NormalDist

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
_cdf = NormalDist().cdf


class SettleAvg(Strategy):
    params = {
        "max_tau": 45,        # trade in the last max_tau .. min_tau seconds
        "min_tau": 4,
        "gap": 0.03,          # required model probability minus (ask + fee), in probability units
        "lo": 0.60,           # price band of the side we buy
        "hi": 0.98,
        "basis_bp": 1.7,      # std of Binance-vs-CF basis change over a window (bp of price)
        "sigma_window": 300,  # seconds of 1 s returns for the volatility estimate (ending 60 s before close)
        "max_entries": 1,
        "slip_c": 0,
    }

    def on_start(self, ctx):
        self.px: dict[str, dict[int, float]] = {}   # series -> {sec: price}, ~7 min
        self.order: dict[str, deque] = {}
        self.basis: dict[str, float] = {}
        self.entries: dict[str, int] = {}

    def _add(self, series, sec, price):
        d = self.px.setdefault(series, {})
        q = self.order.setdefault(series, deque())
        if sec not in d:
            q.append(sec)
        d[sec] = price
        while q and q[0] < sec - 1500:
            d.pop(q.popleft(), None)

    def on_timer(self, ctx):
        now_s = ctx.now // NS
        for series in ctx.spot_map:
            s = ctx.spot(series=series)
            if s is not None:
                self._add(series, now_s, s)
        for m in ctx.markets.values():
            if m.ticker in self.basis or m.strike is None or ctx.now < m.open_ts:
                continue
            d = self.px.get(m.series, {})
            o = m.open_ts // NS
            pre = [d[s] for s in range(o - 60, o) if s in d]
            if len(pre) >= 30:
                self.basis[m.ticker] = m.strike - sum(pre) / len(pre)
        for m in ctx.active_markets():
            self._consider(ctx, m, now_s)

    def _prob(self, m, now_s):
        d = self.px.get(m.series, {})
        ce = m.close_ts // NS
        a = ce - 60
        known, last = [], None
        for s in range(a - 1, now_s):   # rows <= now-1 only
            if s in d:
                last = d[s]
            if last is not None and s >= a:
                known.append(last)
        if last is None or len(known) < now_s - a - 3:
            return None
        n = 60 - len(known)
        if n < 0:
            return None
        rets = []
        prev = None
        for s in range(ce - 60 - self.p.sigma_window, ce - 60):
            v = d.get(s)
            if v is not None:
                if prev is not None and prev > 0:
                    rets.append(math.log(v / prev))
                prev = v
        if len(rets) < 100:
            return None
        mu = sum(rets) / len(rets)
        sg = math.sqrt(sum((r - mu) ** 2 for r in rets) / len(rets))
        exp = (sum(known) + n * last) / 60 + self.basis[m.ticker]
        var = (last * sg) ** 2 * n * (n + 1) * (2 * n + 1) / 6 / 3600
        sd = math.sqrt(var + (last * self.p.basis_bp * 1e-4) ** 2)
        return _cdf((exp - m.strike) / sd)

    def _consider(self, ctx, m, now_s):
        tau = (m.close_ts - ctx.now) / NS
        if not (self.p.min_tau <= tau <= self.p.max_tau) or m.ticker not in self.basis:
            return
        if self.entries.get(m.ticker, 0) >= self.p.max_entries:
            return
        book = ctx.book(m.ticker)
        if book is None or book.best_bid is None or book.best_ask is None:
            return
        P = self._prob(m, now_s)
        if P is None:
            return
        ask, bid = book.best_ask / 1000, book.best_bid / 1000
        fee = lambda p: 0.07 * p * (1 - p)
        eyes = P - ask - fee(ask)          # buy YES
        eno = (1 - P) - (1 - bid) - fee(1 - bid)  # buy NO = sell YES
        if eyes >= eno and eyes >= self.p.gap and self.p.lo <= ask <= self.p.hi:
            side, px, edge = Side.BUY, min(999, book.best_ask + 10 * self.p.slip_c), eyes
        elif eno > eyes and eno >= self.p.gap and self.p.lo <= 1 - bid <= self.p.hi:
            side, px, edge = Side.SELL, max(1, book.best_bid - 10 * self.p.slip_c), eno
        else:
            return
        ctx.record(m.ticker, "P", P * 1000)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"e={edge:.3f}")
            self.entries[m.ticker] = self.entries.get(m.ticker, 0) + 1

    def on_settle(self, ctx, m, pnl):
        self.basis.pop(m.ticker, None)
        self.entries.pop(m.ticker, None)
