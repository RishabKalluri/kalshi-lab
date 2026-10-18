"""BTC / ETH hourly ladder fair value: trade Kalshi's KXBTCD / KXETHD above-X ladders against a lognormal
model around the current EUR/USD price, held to settlement.

Research screen (150-market backfill sample, Jan-Aug 2026): when a plain spot-vol model disagrees with a trade print by more
than 10c the model side netted about +35c/contract (61 markets). Thin FX brackets look priced by inattentive retail.
v2: spot is Binance 1-minute opens (backfill, written to data/ by an offline script, dev dates only). v1 used Yahoo's EURUSD=X hourly OPEN (data/eurusd_1h_open.json, free, research only: a live version needs a real-time
EUR/USD feed). Only bars that opened at or before `now` are used (no lookahead); vol = std of the last `vol_bars` hourly
log returns of those bars, scaled to the time left.

History has trades but no books: the engine synthesizes the top of book from the last trades, so a side is only traded on a
trade that proves that side's quote (taker BUY proves the ask, taker SELL the bid). One entry per market.
Prices are YES mills. ctx.buy = buy YES, ctx.sell = sell YES (= buy NO).
"""
import json
import math
from pathlib import Path

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
DATA = {"KXBTCD": Path(__file__).parent / "data" / "btc_1m_open.json", "KXETHD": Path(__file__).parent / "data" / "eth_1m_open.json"}


def _phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


class CryptoLadder(Strategy):
    params = {
        "edge": 100,        # trade when |model - quote| >= edge mills
        "min_ttc_h": 0.25,  # no entries closer than this to the close
        "max_ttc_h": 24.0,
        "vol_bars": 240,    # one-minute bars for the vol estimate (v2; v1 used 120 hourly bars)
        "max_spread": 400,  # skip stale/one-sided synthetic books (ask - bid, mills)
        "lo_px": 20,        # only quote prices inside [lo_px, hi_px] mills (tick = 10)
        "hi_px": 980,
    }

    def on_start(self, ctx):
        self.feed = {}
        for k, pth in DATA.items():
            ts, px = json.loads(pth.read_text())  # Binance 1-minute opens (first tick of each minute)
            self.feed[k] = (ts, px)
        self.done = set()
        self._vol = {}

    def _spot_vol(self, series, now_s):
        self.ts, self.px = self.feed[series]
        # index of the last bar opened at or before now
        lo, hi = 0, len(self.ts)
        while lo < hi:
            mid = (lo + hi) // 2
            if self.ts[mid] <= now_s:
                lo = mid + 1
            else:
                hi = mid
        i = lo - 1
        if i < self.p.vol_bars + 1:
            return None
        if now_s - self.ts[i] > 180:  # stale feed: don't trust
            return None
        if (series, i) in self._vol:
            sg = self._vol[(series, i)]
        else:
            r = [math.log(self.px[k] / self.px[k - 1]) for k in range(i - self.p.vol_bars + 1, i + 1)]
            mu = sum(r) / len(r)
            sg = math.sqrt(sum((x - mu) ** 2 for x in r) / (len(r) - 1))
            self._vol[(series, i)] = sg
        return self.px[i], sg

    def _prob(self, m, spot, sg, h):
        raw = m.raw or {}
        st = raw.get("strike_type")
        lo, hi = raw.get("floor_strike"), raw.get("cap_strike")
        s = sg * math.sqrt(max(h * 60, 3.0))  # sg is per minute

        def above(k):
            return 1 - _phi(math.log(k / spot) / s)

        if st == "between" and lo is not None and hi is not None:
            return above(lo) - above(hi)
        if st in ("greater", "greater_or_equal") and lo is not None:
            return above(lo)
        if st in ("less", "less_or_equal") and hi is not None:
            return 1 - above(hi)
        return None

    def on_trade(self, ctx, tr):
        t = tr.ticker
        m = ctx.markets.get(t)
        if m is None or m.result is not None or t in self.done:
            return
        h = ctx.seconds_left(t) / 3600
        if h > self.p.max_ttc_h or h < self.p.min_ttc_h:
            return
        book = ctx.book(t)
        if book is None or book.best_bid is None or book.best_ask is None:
            return
        bid, ask = book.best_bid, book.best_ask
        if ask - bid > self.p.max_spread:
            return
        sv = self._spot_vol(m.series, ctx.now // NS)
        if sv is None:
            return
        q = self._prob(m, sv[0], sv[1], h)
        if q is None:
            return
        q *= 1000
        if tr.taker == Side.BUY and q - ask >= self.p.edge and self.p.lo_px <= ask <= self.p.hi_px:
            qty = ctx.size(t, Side.BUY, ask, tif=TIF.IOC)
            if qty >= 1 and ctx.buy(t, ask, qty, tif=TIF.IOC, tag="yes") is not None:
                self.done.add(t)
        elif tr.taker == Side.SELL and bid - q >= self.p.edge and self.p.lo_px <= bid <= self.p.hi_px:
            qty = ctx.size(t, Side.SELL, bid, tif=TIF.IOC)
            if qty >= 1 and ctx.sell(t, bid, qty, tif=TIF.IOC, tag="no") is not None:
                self.done.add(t)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
