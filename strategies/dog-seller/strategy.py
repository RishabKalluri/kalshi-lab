"""Underdog Seller: passively sell 10-30c underdogs to lottery-ticket takers, mid-window, for zero maker fees.

Research (development data, both ETH and SOL): taker purchases of 10-30c contracts lose 2-4c/contract at real
fills; the passive side of those trades earned +1.3..+2.1c/contract 6-15 minutes before close, 7-8/8 months
positive. This strategy joins the underdog's best offer with one post-only order per market and holds to
settlement.

Prices are YES mills. Selling YES = offering YES (the underdog when YES < 50c). Buying YES at the bid =
offering NO (the underdog when YES > 50c).
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
_inv = NormalDist().inv_cdf


class DogSeller(Strategy):
    params = {
        "min_tau": 360,     # stop quoting (cancel) this many seconds before close
        "max_tau": 870,     # start quoting this many seconds before close
        "dog_lo": 100,      # underdog price range we sell (mills of the underdog contract)
        "dog_hi": 300,
        "series": "",       # comma list to restrict trading (e.g. KXETH15M); "" = all configured series
        # Protection: pull the quote when the last `lookback_s` of spot implies the YES price moves toward the
        # underdog by more than `protect` mills (delta from the market's own price and EWMA vol). 0 = off.
        "protect": 0,
        "lookback_s": 3.0,
        "cooldown_s": 5.0,
        "vol_halflife_s": 300,
    }

    def on_start(self, ctx):
        self.quote = {}  # ticker -> live Order
        self.allowed = set(s for s in self.p.series.split(",") if s) if self.p.series else None
        self.hist = {}    # series -> deque of (ns, spot)
        self.var = {}     # series -> EWMA variance of 1s spot changes
        self.last1s = {}  # series -> (sec, spot) for the 1s vol sampler
        self.pulled = {}  # ticker -> ns until which we don't quote

    def _want(self, ctx, m):
        """(side, price) of the order we want resting, or None."""
        if self.pulled.get(m.ticker, 0) > ctx.now:
            return None
        tau = (m.close_ts - ctx.now) / NS
        if not (self.p.min_tau <= tau <= self.p.max_tau):
            return None
        book = ctx.book(m.ticker)
        if book is None or book.best_bid is None or book.best_ask is None or book.best_ask <= book.best_bid:
            return None
        mid = (book.best_bid + book.best_ask) / 2
        if mid < 500:  # YES is the underdog: offer YES at its ask
            dog = book.best_ask
            return (Side.SELL, book.best_ask) if self.p.dog_lo <= dog <= self.p.dog_hi else None
        dog = 1000 - book.best_bid  # NO is the underdog: offer NO at its ask = bid YES at the YES bid
        return (Side.BUY, book.best_bid) if self.p.dog_lo <= dog <= self.p.dog_hi else None

    def _sync(self, ctx, m):
        if self.allowed is not None and m.series not in self.allowed:
            return
        want = self._want(ctx, m)
        cur = self.quote.get(m.ticker)
        if cur is not None and not cur.is_live:
            cur = self.quote.pop(m.ticker)
            cur = None
        if cur is not None:
            if want is not None and cur.side == want[0] and cur.price == want[1]:
                return
            ctx.cancel(cur)
            self.quote.pop(m.ticker, None)
        if want is None:
            return
        side, px = want
        qty = ctx.size(m.ticker, side, px, tif=TIF.POST)
        if qty >= 1:
            o = (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.POST, tag="dog")
            if o is not None:
                self.quote[m.ticker] = o
        book = ctx.book(m.ticker)
        if book is not None and book.mid is not None:
            ctx.record(m.ticker, "mid", book.mid)

    def on_book(self, ctx, ticker, book):
        m = ctx.markets.get(ticker)
        if m is not None and m.open_ts <= ctx.now < m.close_ts:
            self._sync(ctx, m)

    def _yes_move(self, ctx, m, move):
        """Expected YES price move (mills) for a spot move of `move` dollars, from the market's own price."""
        var = self.var.get(m.series)
        book = ctx.book(m.ticker)
        if not var or book is None or book.mid is None:
            return 0.0
        tau = max(41.0, (m.close_ts - ctx.now) / NS)
        z = _inv(min(max(book.mid / 1000, 0.01), 0.99))
        dens = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
        return 1000 * dens * move / (math.sqrt(var) * math.sqrt(tau - 40))

    def on_spot(self, ctx, tick):
        if not self.p.protect:
            return
        for series, sources in ctx.spot_map.items():
            if tick.source not in sources:
                continue
            s = ctx.spot(series=series)
            if s is None:
                continue
            h = self.hist.setdefault(series, deque())
            h.append((ctx.now, s))
            cut = ctx.now - int(self.p.lookback_s * NS)
            while len(h) > 1 and h[1][0] <= cut:
                h.popleft()
            move = s - h[0][1]
            for m in ctx.active_markets(series):
                o = self.quote.get(m.ticker)
                if o is None or not o.is_live:
                    continue
                dy = self._yes_move(ctx, m, move)
                # selling YES (YES underdog) is hurt by YES rising; bidding YES (NO underdog) by YES falling
                toward_dog = dy if o.side == Side.SELL else -dy
                if toward_dog > self.p.protect:
                    ctx.cancel(o)
                    self.quote.pop(m.ticker, None)
                    self.pulled[m.ticker] = ctx.now + int(self.p.cooldown_s * NS)

    def on_timer(self, ctx):
        sec = ctx.now // NS
        a = 1 - 0.5 ** (1 / self.p.vol_halflife_s)
        for series in ctx.spot_map:
            s = ctx.spot(series=series)
            if s is None:
                continue
            prev = self.last1s.get(series)
            if prev is not None and sec > prev[0]:
                r2 = (s - prev[1]) ** 2 / (sec - prev[0])
                v = self.var.get(series)
                self.var[series] = r2 if v is None else (1 - a) * v + a * r2
            self.last1s[series] = (sec, s)
        for m in ctx.active_markets():
            self._sync(ctx, m)

    def on_settle(self, ctx, m, pnl):
        self.quote.pop(m.ticker, None)
        self.pulled.pop(m.ticker, None)
