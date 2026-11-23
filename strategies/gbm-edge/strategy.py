"""Learned-edge taker on the thin 15-minute crypto markets (SOL, XRP, DOGE).

Two gradient-boosted regressors (fit() before each month on earlier data only) predict the net edge, after the taker
fee, of buying YES at the ask and of buying NO at the bid, from the spot's distance to the strike measured in
5-minute and 60-minute realized-vol units, the market's mid and the time left. At fixed checkpoints, take the better
side when its predicted edge exceeds `thr`; one entry per market, held to settlement.
"""
import math
import pickle
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
PARAMS = Path(__file__).parent / "params"


class _Hist:
    """1s spot samples (last ~2h) with running sum of squared changes; gap-safe like eth-volfav2."""
    KEEP = 2 * 3600 + 120

    def __init__(self):
        self.secs, self.px, self.cum = [], [], [0.0]

    def add(self, sec, price):
        if self.px:
            gap = max(1, sec - self.secs[-1])
            self.cum.append(self.cum[-1] + (price - self.px[-1]) ** 2 / gap)
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

    def rv(self, window):
        n = min(window, len(self.cum) - 1)
        if n < min(window, 300) // 2:
            return None
        return math.sqrt((self.cum[-1] - self.cum[-1 - n]) / n)


class GbmEdge(Strategy):
    @classmethod
    def fit(cls, series: list[str], until: str | None) -> dict:
        from gbm_fit import fit_model
        return {"model": fit_model(series, until)}

    params = {
        "model": "",
        "thr": 0.03,            # predicted net edge (probability units) needed to trade
        "checkpoints": [600, 480, 360, 300, 240, 180, 120, 90, 60],
        "min_hist_s": 3600,
        "rv_scale": 1.0,
        "max_entries": 1,
        "slip_c": 0,
    }

    def on_start(self, ctx):
        self.hist = {}
        self.basis = {}
        self.entries = {}
        self.mdl = None
        if ctx.spot_history:
            for series in ctx.spot_map:
                h = self.hist.setdefault(series, _Hist())
                for sec, px in ctx.spot_history(series, 2 * 3600):
                    h.add(sec, px)

    def _model(self):
        if self.mdl is None:
            with open(PARAMS / self.p.model, "rb") as f:
                self.mdl = pickle.load(f)
        return self.mdl

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
        for m in ctx.active_markets():
            self._consider(ctx, m, now_s)

    def _consider(self, ctx, m, now_s):
        tau = (m.close_ts - ctx.now) / NS
        if int(round(tau)) not in self.p.checkpoints or m.ticker not in self.basis:
            return
        if len(self.entries.get(m.ticker, [])) >= self.p.max_entries:
            return
        h = self.hist.get(m.series)
        book = ctx.book(m.ticker)
        if not h or book is None or book.best_bid is None or book.best_ask is None:
            return
        if h.secs[-1] - h.secs[0] < self.p.min_hist_s:
            return
        rv5, rv60 = h.rv(300), h.rv(3600)
        if not (rv5 and rv60):
            return
        rv5, rv60 = rv5 * self.p.rv_scale, rv60 * self.p.rv_scale
        bid, ask = book.best_bid / 1000, book.best_ask / 1000
        D = h.px[-1] + self.basis[m.ticker] - m.strike
        h_ = int(round(tau))
        x = [[D / (rv5 * math.sqrt(h_) + 1e-12), D / (rv60 * math.sqrt(h_) + 1e-12), (bid + ask) / 2, h_]]
        md = self._model()
        ey = float(md["yes"].predict(x)[0])
        en = float(md["no"].predict(x)[0])
        ctx.record(m.ticker, "edge", max(ey, en))
        if max(ey, en) <= self.p.thr:
            return
        if ey >= en:
            side, px = Side.BUY, min(999, book.best_ask + 10 * self.p.slip_c)
        else:
            side, px = Side.SELL, max(1, book.best_bid - 10 * self.p.slip_c)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"e={max(ey, en):.3f}")
            self.entries.setdefault(m.ticker, []).append(now_s)

    def on_settle(self, ctx, m, pnl):
        self.basis.pop(m.ticker, None)
        self.entries.pop(m.ticker, None)
