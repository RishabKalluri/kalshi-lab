"""Take liquidity when the model's P(up) disagrees with the book by more than `edge`.

Fair value comes from composite spot (median across exchanges), EWMA realized vol and the
averaging settlement rule (see models.py). Buys YES when fair - ask > edge, sells YES when
bid - fair > edge, IOC, up to `max_pos` contracts per market.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from models import VolEstimator, WindowAverager, prob_up  # noqa: E402

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class FairValue(Strategy):
    params = {
        "edge": 40,            # mills of edge required to trade (40 = 4 cents)
        "max_pos": 50,         # abs contracts per market
        "min_tau": 20,         # stop trading this many seconds before close
        "max_tau": 840,        # don't trade the first minute after open
        "vol_halflife": 300,
        "cooldown_s": 2,       # min seconds between orders per market
        "basis": True,         # correct spot->index basis using the strike vs our own opening average
    }

    def on_start(self, ctx):
        self.vol = VolEstimator(self.p.vol_halflife)
        self.win: dict[str, WindowAverager] = {}
        self.open_avg: dict[str, WindowAverager] = {}
        self.last_order: dict[str, int] = {}
        self.fair: dict[str, float] = {}

    def on_timer(self, ctx):
        s = ctx.spot()
        if s is None:
            return
        now_s = ctx.now // NS
        self.vol.update(s, now_s)
        sigma = self.vol.sigma
        for t, m in ctx.markets.items():
            # Record our own spot during each market's opening and closing 60s windows.
            open_s, close_s = m.open_ts // NS, m.close_ts // NS
            if open_s - 60 <= now_s < open_s:
                self.open_avg.setdefault(t, WindowAverager()).add(now_s, s)
            if close_s - 60 <= now_s < close_s:
                self.win.setdefault(t, WindowAverager()).add(now_s, s)
        if sigma is None or self.vol.last_t is None:
            return
        for m in ctx.active_markets():
            if m.strike is None:
                continue
            tau = (m.close_ts - ctx.now) / NS
            book = ctx.book(m.ticker)
            if book is None:
                continue
            basis = 0.0
            if self.p.basis and m.ticker in self.open_avg:
                osum, on = self.open_avg[m.ticker].stats(m.open_ts // NS)
                if on >= 30:
                    basis = m.strike - osum / on  # index minus our composite
            wsum, wn = self.win.get(m.ticker, WindowAverager()).stats(m.close_ts // NS)
            fair = 1000 * prob_up(s + basis, m.strike, tau, sigma, wsum + basis * wn, wn)
            self.fair[m.ticker] = fair
            if not (self.p.min_tau <= tau <= self.p.max_tau):
                continue
            if ctx.now - self.last_order.get(m.ticker, 0) < self.p.cooldown_s * NS:
                continue
            pos = ctx.position(m.ticker)
            ask, bid = book.best_ask, book.best_bid
            if ask is not None and fair - ask > self.p.edge and self.p.max_pos - pos >= 1:
                qty = min(ctx.size(m.ticker, Side.BUY, ask, prob=fair / 1000, tif=TIF.IOC), self.p.max_pos - pos)
                if qty >= 1 and ctx.buy(m.ticker, ask, qty, tif=TIF.IOC, tag=f"fv={fair:.0f}"):
                    self.last_order[m.ticker] = ctx.now
            elif bid is not None and bid - fair > self.p.edge and self.p.max_pos + pos >= 1:
                qty = min(ctx.size(m.ticker, Side.SELL, bid, prob=fair / 1000, tif=TIF.IOC), self.p.max_pos + pos)
                if qty >= 1 and ctx.sell(m.ticker, bid, qty, tif=TIF.IOC, tag=f"fv={fair:.0f}"):
                    self.last_order[m.ticker] = ctx.now

    def on_settle(self, ctx, m, pnl):
        for d in (self.win, self.open_avg, self.last_order, self.fair):
            d.pop(m.ticker, None)
