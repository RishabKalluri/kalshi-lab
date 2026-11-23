"""XRP tie model: model P(YES) for KXXRP15M in the last seconds and buy YES when the ask is below it.

Settlement: YES if round4(avg of 60 CF prices before the close) >= K, where K is the same quantity for the open (already rounded).
So P(YES) = P(avg >= K - 0.5 tick): a half-tick shift that matters when the estimate is within a few ticks of K. The estimate is the spot feed's
60 s average (seconds already known + the last price for the rest), multiplied by a basis ratio (CF value / spot average) taken from the last
few strikes (the strike of a window is the CF average before its open, and the spot average over the same minute gives the ratio).
Residual sd of the estimate: ~1.1 bp at <=8 s left, rising to ~1.4 bp at 30 s (dev data, Binance XRPUSDT vs CF).
Prices are YES mills.
"""

from collections import deque
from math import erf, sqrt

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
TICK = 1e-4
# (seconds left, residual sd in bp of price)
SIG = [(3, 1.12), (8, 1.12), (20, 1.25), (30, 1.42), (45, 1.9), (60, 2.4)]


def sigma_bp(s):
    if s <= SIG[0][0]:
        return SIG[0][1]
    for (a, x), (b, y) in zip(SIG, SIG[1:]):
        if s <= b:
            return x + (y - x) * (s - a) / (b - a)
    return SIG[-1][1]


def phi(z):
    return 0.5 * (1 + erf(z / sqrt(2)))


def fee(p):
    return 0.07 * p * (1 - p)


class XrpTieModel(Strategy):
    params = {
        "max_s": 30.0,
        "min_s": 3.0,
        "edge": 0.04,       # required model P(YES) - ask - fee
        "lo": 50,           # ask range, mills
        "hi": 970,
        "fresh_s": 3.0,     # the ask must come from a taker buy within this many seconds
        "nratio": 4,        # windows used for the basis ratio (own open + 3 earlier)
        "sig_mult": 1.0,
        "tick_shift": 0.5,  # ticks: ties resolve YES
        "both": 0,          # 1: also buy NO when the model says so
        "maxn": 1,          # entries per market
    }

    def on_start(self, ctx):
        self.series = None
        self.px = {}            # second -> composite spot price
        self.order_q = deque()  # seconds, for trimming
        self.ratio = {}         # open second -> CF/spot ratio
        self.last_buy = {}      # ticker -> ns of last taker-buy trade
        self.last_sell = {}
        self.n = {}

    # --- spot history -------------------------------------------------
    def on_timer(self, ctx):
        if self.series is None:
            ser = list(ctx.spot_map)
            self.series = ser[0] if ser else None
            if self.series is None:
                return
        sec = ctx.now // NS
        if sec in self.px:
            return
        p = ctx.spot(series=self.series)
        if p is None:
            return
        self.px[sec] = p
        self.order_q.append(sec)
        while self.order_q and self.order_q[0] < sec - 5400:
            self.px.pop(self.order_q.popleft(), None)
        self._ratios(ctx, sec)

    def _avg60(self, end):
        """Mean spot over seconds end-60..end-1, or None if too sparse."""
        v = [self.px[s] for s in range(end - 60, end) if s in self.px]
        return sum(v) / len(v) if len(v) >= 55 else None

    def _ratios(self, ctx, sec):
        for m in ctx.active_markets(self.series):
            o = m.open_ts // NS
            if o in self.ratio or m.strike is None or sec < o + 2:
                continue
            a = self._avg60(o)
            if a:
                self.ratio[o] = m.strike / a

    # --- model --------------------------------------------------------
    def _pyes(self, ctx, m, now_s, s):
        o = m.open_ts // NS
        rs = [self.ratio[o - 900 * j] for j in range(int(self.p.nratio)) if (o - 900 * j) in self.ratio]
        if len(rs) < 2 or m.strike is None:
            return None
        b = sum(rs) / len(rs)
        close = m.close_ts // NS
        known = [self.px[t] for t in range(close - 60, int(now_s)) if t in self.px]
        nk = len(known)
        if nk < 25 or nk > 60:
            return None
        last = known[-1]
        est = (sum(known) + last * (60 - nk)) / 60 * b
        sd = est * sigma_bp(s) * self.p.sig_mult * 1e-4
        z = (est - (m.strike - self.p.tick_shift * TICK)) / sd
        return phi(z)

    # --- trading ------------------------------------------------------
    def on_trade(self, ctx, tr):
        t = tr.ticker
        if tr.taker == Side.BUY:
            self.last_buy[t] = ctx.now
        else:
            self.last_sell[t] = ctx.now
        m = ctx.markets.get(t)
        if m is None or m.result is not None or self.n.get(t, 0) >= self.p.maxn:
            return
        s = ctx.seconds_left(t)
        if s > self.p.max_s or s < self.p.min_s:
            return
        book = ctx.book(t)
        if book is None or book.best_bid is None or book.best_ask is None:
            return
        pm = self._pyes(ctx, m, ctx.now / NS, s)
        if pm is None:
            return
        bid, ask = book.best_bid, book.best_ask
        fresh = self.p.fresh_s * NS
        if ctx.now - self.last_buy.get(t, -10**18) <= fresh and self.p.lo <= ask <= self.p.hi:
            a = ask / 1000
            if pm - a - fee(a) >= self.p.edge:
                qty = ctx.size(t, Side.BUY, ask, tif=TIF.IOC)
                if qty >= 1 and ctx.buy(t, ask, qty, tif=TIF.IOC, tag="tiey") is not None:
                    self.n[t] = self.n.get(t, 0) + 1
                    ctx.record(t, "pm", pm)
                    return
        if self.p.both and ctx.now - self.last_sell.get(t, -10**18) <= fresh and self.p.lo <= 1000 - bid <= self.p.hi:
            c = (1000 - bid) / 1000
            if (1 - pm) - c - fee(c) >= self.p.edge:
                qty = ctx.size(t, Side.SELL, bid, tif=TIF.IOC)
                if qty >= 1 and ctx.sell(t, bid, qty, tif=TIF.IOC, tag="tien") is not None:
                    self.n[t] = self.n.get(t, 0) + 1
