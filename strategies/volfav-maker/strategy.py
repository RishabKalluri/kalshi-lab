"""VolFav Maker: eth-volfav's signal, executed as a maker one tick inside the spread instead of taking the ask.

Signal (identical to strategies/eth-volfav, same vol model and 70th-percentile threshold, refit monthly):
  at fixed checkpoints T-360..T-60 s, implied vol iv = D / (Phi^-1(mid) sqrt(tau-40)) vs a HAR forecast; when
  iv / forecast > threshold, the favourite is underpriced.
Execution (the new part): post a post-only bid for the favourite one tick above its best bid (first in the queue;
join the bid when the spread is one tick), cancel it after `ttl_s` or near close. A maker pays no fee and doesn't
cross the spread (together ~3-5c on ETH at these prices), versus a taker's ~+2c edge. The risk is adverse
selection: we only fill when someone sells the favourite to us. Research (vol-burst/research/maker_fav2.py, dev
data): signal rows filled 45-60% of the time (May-Aug) at +2.3..+4.2c/contract vs +0.6..+2.9c for the taker;
non-signal rows lose (-1..-1.7c), so the signal, not the maker rebate, is what carries it.

Prices are YES mills (0..1000). ctx.buy = buy YES, ctx.sell = sell YES (= buy NO).
"""

import json
import math
import sys
from pathlib import Path
from statistics import NormalDist

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
TICK = 10
PARAMS = Path(__file__).parent / "params"
_inv = NormalDist().inv_cdf


class _Hist:
    """1s spot samples for the last ~4h with a running sum of squared changes (as eth-volfav)."""
    KEEP = 4 * 3600 + 120

    def __init__(self):
        self.secs, self.px, self.cum = [], [], [0.0]

    def add(self, sec, price):
        if self.px:
            self.cum.append(self.cum[-1] + (price - self.px[-1]) ** 2)
        self.secs.append(sec)
        self.px.append(price)
        if len(self.secs) > 2 * self.KEEP:
            k = len(self.secs) - self.KEEP
            self.secs, self.px = self.secs[k:], self.px[k:]
            base = self.cum[k]
            self.cum = [0.0] + [c - base for c in self.cum[k + 1:]]

    def window(self, a, b):
        import bisect
        i, j = bisect.bisect_left(self.secs, a), bisect.bisect_left(self.secs, b)
        return self.px[i:j]


class VolFavMaker(Strategy):
    @classmethod
    def fit(cls, series: list[str], until: str | None) -> dict:
        from vol_fit import fit_model
        return {"model": fit_model(series[0], until, pct=0.7)}

    params = {
        "model": "",
        "min_tau": 60,
        "max_tau": 360,
        "max_entries": 7,       # placements per market
        "threshold_mult": 1.0,
        "min_hist_s": 3600,
        "rv_scale": 1.0,
        "checkpoints": [360, 300, 240, 180, 120, 90, 60],
        "ttl_s": 25,            # cancel an unfilled quote after this many seconds (checkpoints are >= 30 s apart)
        "stop_tau": 45,         # cancel everything this close to the close
        "improve": 1,           # ticks above the favourite's best bid (0 = join the bid)
        "take": 0,              # 1 = eth-volfav's taker execution (IOC at the ask), for like-for-like comparison
    }

    def on_start(self, ctx):
        self.hist: dict = {}
        self.models: dict = {}
        self.basis: dict = {}
        self.entries: dict = {}
        self.quotes: dict = {}   # ticker -> (order, placed_s)
        if ctx.spot_history:
            for series in ctx.spot_map:
                pts = ctx.spot_history(series, 4 * 3600)
                h = self.hist.setdefault(series, _Hist())
                for sec, px in pts:
                    h.add(sec, px)

    def _model(self, series):
        if series not in self.models:
            name = self.p.model or f"vol_model_{series}.json"
            self.models[series] = json.loads((PARAMS / name).read_text())
        return self.models[series]

    def _rv(self, h, window):
        n = min(window, len(h.cum) - 1)
        if n < min(window, 300) // 2:
            return None
        return math.sqrt((h.cum[-1] - h.cum[-1 - n]) / n)

    def on_timer(self, ctx):
        now_s = ctx.now // NS
        for series in ctx.spot_map:
            s = ctx.spot(series=series)
            if s is not None:
                self.hist.setdefault(series, _Hist()).add(now_s, s)
        for m in ctx.markets.values():
            if m.ticker in self.basis or m.strike is None or ctx.now < m.open_ts:
                continue
            h = self.hist.get(m.series)
            pre = h.window(m.open_ts // NS - 60, m.open_ts // NS) if h else []
            if len(pre) >= 30:
                self.basis[m.ticker] = m.strike - sum(pre) / len(pre)
        # expire quotes
        for tk, (o, t0) in list(self.quotes.items()):
            if not o.is_live:
                self.quotes.pop(tk)
            elif now_s - t0 >= self.p.ttl_s or ctx.seconds_left(tk) < self.p.stop_tau:
                ctx.cancel(o)
                self.quotes.pop(tk)
        for m in ctx.active_markets():
            self._consider(ctx, m, now_s)

    def _signal(self, ctx, m, tau, book):
        h = self.hist.get(m.series)
        if not h or h.secs[-1] - h.secs[0] < self.p.min_hist_s:
            return None
        rv15, rv60 = self._rv(h, 900), self._rv(h, 3600)
        rv4h = self._rv(h, 14400) or rv60
        if not (rv15 and rv60 and rv4h):
            return None
        rv15, rv60, rv4h = (x * self.p.rv_scale for x in (rv15, rv60, rv4h))
        mid = (book.best_bid + book.best_ask) / 2000
        if not (0.03 < mid < 0.97 and abs(mid - 0.5) > 0.07):
            return None
        D = h.px[-1] + self.basis[m.ticker] - m.strike
        z = _inv(mid)
        if z * D <= 0:
            return None
        iv = D / (z * math.sqrt(tau - 40))
        md = self._model(m.series)
        hour = (m.close_ts // NS // 3600) % 24
        x = [1.0, math.log(rv15), math.log(rv60), math.log(rv4h)] + [1.0 if hour == hh else 0.0 for hh in range(1, 24)] + [math.log(tau)]
        ratio = iv / math.exp(sum(b * v for b, v in zip(md["beta"], x)))
        ctx.record(m.ticker, "ratio", ratio)
        return ratio if ratio > md["ratio_threshold"] * self.p.threshold_mult else None

    def _consider(self, ctx, m, now_s):
        tau = (m.close_ts - ctx.now) / NS
        if not (self.p.min_tau <= tau <= self.p.max_tau) or m.ticker not in self.basis:
            return
        if self.p.checkpoints and int(round(tau)) not in self.p.checkpoints:
            return
        if m.ticker in self.quotes:
            return
        ent = self.entries.setdefault(m.ticker, 0)
        if ent >= self.p.max_entries:
            return
        book = ctx.book(m.ticker)
        if book is None or book.best_bid is None or book.best_ask is None:
            return
        ratio = self._signal(ctx, m, tau, book)
        if ratio is None:
            return
        spread_ticks = (book.best_ask - book.best_bid) // TICK
        imp = min(self.p.improve, max(0, spread_ticks - 1)) * TICK
        if book.best_bid + book.best_ask > 1000:   # favourite = YES: bid for YES
            side, px = Side.BUY, book.best_bid + imp
        else:                                        # favourite = NO: offer YES (= bid for NO)
            side, px = Side.SELL, book.best_ask - imp
        if self.p.take:
            px = book.best_ask if side == Side.BUY else book.best_bid
            qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
            if qty >= 1:
                (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"take r={ratio:.2f}")
                self.entries[m.ticker] = ent + 1
            return
        qty = ctx.size(m.ticker, side, px, tif=TIF.POST)
        if qty >= 1:
            o = (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.POST, tag=f"r={ratio:.2f}")
            if o is not None:
                self.quotes[m.ticker] = (o, now_s)
                self.entries[m.ticker] = ent + 1

    def on_settle(self, ctx, m, pnl):
        self.basis.pop(m.ticker, None)
        self.entries.pop(m.ticker, None)
        self.quotes.pop(m.ticker, None)
