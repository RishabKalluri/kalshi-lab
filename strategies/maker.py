"""Passive market maker with spot-driven quote protection.

Why this can work: makers pay no fees on these series while takers pay ~1.75c at 50c, and
recorded markouts show resting liquidity earns a small positive markout on average.
Why it can fail: fast traders pick off stale quotes when spot moves. So:

* Quote at the touch (join best bid/ask, or step one tick inside when the spread is wide).
  The market's own price is the reference: our spot model is *worse* than the market at
  pricing (see scripts/model_vs_market.py), so we don't use it for levels.
* Protection: on every spot tick, translate the recent spot move into an expected YES move
  (delta = dP/dS from the market's implied probability and realized vol). If that move is
  against a resting quote by more than `protect` ticks, pull that side for `cooldown_s`.
* Inventory: stop adding to a side beyond `skew_pos`, never exceed `max_pos`.
* Only quote mid-life (skip the first minute and the settlement window) and away from the
  price tails where one tick is a large fraction of the price.
"""

import math
import statistics
import sys
from collections import deque
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from models import VolEstimator  # noqa: E402

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.recorder.config import settlement  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
TICK = 10  # $0.01 in the 0.10-0.90 range


def inv_norm(p: float) -> float:
    """Inverse standard normal CDF (Acklam's approximation, |error| < 1.2e-9)."""
    p = min(max(p, 1e-9), 1 - 1e-9)
    a = [-3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02, 1.383577518672690e+02,
         -3.066479806614716e+01, 2.506628277459239e+00]
    b = [-5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02, 6.680131188771972e+01,
         -1.328068155288572e+01]
    c = [-7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00, -2.549732539343734e+00,
         4.374664141464968e+00, 2.938163982698783e+00]
    d = [7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00, 3.754408661907416e+00]
    lo, hi = 0.02425, 1 - 0.02425
    if p < lo:
        q = math.sqrt(-2 * math.log(p))
        return (((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    if p > hi:
        q = math.sqrt(-2 * math.log(1 - p))
        return -(((((c[0]*q+c[1])*q+c[2])*q+c[3])*q+c[4])*q+c[5]) / ((((d[0]*q+d[1])*q+d[2])*q+d[3])*q+1)
    q = p - 0.5
    r = q * q
    return (((((a[0]*r+a[1])*r+a[2])*r+a[3])*r+a[4])*r+a[5])*q / (((((b[0]*r+b[1])*r+b[2])*r+b[3])*r+b[4])*r+1)


class SpreadMaker(Strategy):
    params = {
        "max_pos": 50,        # hard cap on |position| per market
        "skew_pos": 20,       # beyond this, only quote the side that reduces inventory
        "min_tau": 120,       # stop quoting this many seconds before close
        "max_tau": 840,       # start quoting 60s after open
        "min_mid": 300,       # only quote when the mid is inside [min_mid, max_mid] (mills)
        "max_mid": 700,
        "improve_spread": 30, # step one tick inside when the spread is at least this wide
        "protect": 0.25,      # pull a side when the expected adverse move exceeds this many ticks
        "lookback_s": 2.0,    # spot move window for protection
        "cooldown_s": 3.0,    # how long a pulled side stays out
        "vol_halflife": 300,
        "flatten": False,     # at min_tau, cross the spread to flatten instead of holding to settlement
        # Model gating (gold): skip a side when the spot model says it's the wrong side of fair by > gate mills.
        # Gold settles on one print, so P(yes) = Phi((S - S_open) / sqrt(k^2 sigma^2 tau + b^2)); k, b fitted
        # in research/gold_robust.py. None disables gating.
        "gate": None,
        "gate_k": 1.03,
        "gate_b": 0.56,
    }

    def on_start(self, ctx):
        self.vol: dict[str, VolEstimator] = {}
        self.hist: dict[str, deque] = {}          # series -> (ts, spot)
        self.quotes: dict[str, dict] = {}         # ticker -> {"bid": Order, "ask": Order}
        self.pulled: dict[tuple[str, str], int] = {}  # (ticker, side) -> pulled until ts
        self.flattened: set[str] = set()
        self.open_spot: dict[str, float] = {}     # ticker -> spot at the market's open (gating model)

    def _model_fair(self, ctx, m) -> float | None:
        s0 = self.open_spot.get(m.ticker)
        v = self.vol.get(m.series)
        s = ctx.spot(series=m.series)
        if s0 is None or s is None or not v or not v.sigma:
            return None
        tau = max(1.0, (m.close_ts - ctx.now) / NS)
        sd = math.sqrt(self.p.gate_k ** 2 * v.sigma ** 2 * tau + self.p.gate_b ** 2)
        return 1000 * 0.5 * (1 + math.erf((s - s0) / sd / math.sqrt(2)))

    # --- helpers -----------------------------------------------------------
    def _delta_ticks(self, ctx, m, book, move: float) -> float:
        """Expected YES move in ticks for a spot move of `move` dollars."""
        v = self.vol.get(m.series)
        sigma = v.sigma if v else None
        mid = book.mid
        if not sigma or mid is None:
            return 0.0
        tau = max(1.0, (m.close_ts - ctx.now) / NS)
        point = settlement(m.series) == "point"  # single-print settlement; crypto settles on a 60s average
        sd = sigma * (math.sqrt(tau) if point else math.sqrt(max(tau - 60, 0) + 20))
        z = inv_norm(mid / 1000)
        dens = math.exp(-z * z / 2) / math.sqrt(2 * math.pi)
        return 1000 * dens / sd * move / TICK

    def _cancel(self, ctx, ticker, side):
        o = self.quotes.get(ticker, {}).pop(side, None)
        if o is not None and o.is_live:
            ctx.cancel(o)

    # --- hooks -------------------------------------------------------------
    def on_spot(self, ctx, tick):
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
                book = ctx.book(m.ticker)
                if book is None:
                    continue
                exp = self._delta_ticks(ctx, m, book, move)
                until = ctx.now + int(self.p.cooldown_s * NS)
                if exp < -self.p.protect:    # YES about to fall: our bid gets hit
                    self.pulled[(m.ticker, "bid")] = until
                    self._cancel(ctx, m.ticker, "bid")
                elif exp > self.p.protect:   # YES about to rise: our ask gets lifted
                    self.pulled[(m.ticker, "ask")] = until
                    self._cancel(ctx, m.ticker, "ask")

    def on_timer(self, ctx):
        now_s = ctx.now / NS
        for series in ctx.spot_map:
            s = ctx.spot(series=series)
            if s is not None:
                self.vol.setdefault(series, VolEstimator(self.p.vol_halflife)).update(s, now_s)
        for m in ctx.markets.values():
            if m.ticker not in self.open_spot and ctx.now >= m.open_ts:
                s = ctx.spot(series=m.series)
                if s is not None and ctx.now - m.open_ts < 5 * NS:  # only if we saw the open
                    self.open_spot[m.ticker] = s
        for m in ctx.active_markets():
            book = ctx.book(m.ticker)
            tau = (m.close_ts - ctx.now) / NS
            pos = ctx.position(m.ticker)
            if book is None or book.best_bid is None or book.best_ask is None:
                continue
            ctx.record(m.ticker, "fair", book.mid)
            if tau < self.p.min_tau:
                for side in ("bid", "ask"):
                    self._cancel(ctx, m.ticker, side)
                if self.p.flatten and abs(pos) >= 1 and m.ticker not in self.flattened:
                    self.flattened.add(m.ticker)
                    if pos > 0:
                        ctx.sell(m.ticker, book.best_bid, abs(pos), tif=TIF.IOC, tag="flatten")
                    else:
                        ctx.buy(m.ticker, book.best_ask, abs(pos), tif=TIF.IOC, tag="flatten")
                continue
            if tau > self.p.max_tau:
                continue
            bid, ask = book.best_bid, book.best_ask
            if not (self.p.min_mid <= (bid + ask) / 2 <= self.p.max_mid):
                for side in ("bid", "ask"):
                    self._cancel(ctx, m.ticker, side)
                continue
            if ask - bid >= self.p.improve_spread:
                bid, ask = bid + TICK, ask - TICK
            fair = self._model_fair(ctx, m) if self.p.gate is not None else None
            if fair is not None:
                ctx.record(m.ticker, "model", fair)
            want = {
                "bid": bid if pos < self.p.skew_pos and self.p.max_pos - pos >= 1 else None,
                "ask": ask if pos > -self.p.skew_pos and self.p.max_pos + pos >= 1 else None,
            }
            if fair is not None:
                if fair < bid - self.p.gate:
                    want["bid"] = None  # model: YES worth less than we'd pay
                if fair > ask + self.p.gate:
                    want["ask"] = None  # model: YES worth more than we'd sell at
            q = self.quotes.setdefault(m.ticker, {})
            for side, px in want.items():
                if self.pulled.get((m.ticker, side), 0) > ctx.now:
                    px = None
                cur = q.get(side)
                if cur is not None and not cur.is_live:
                    q.pop(side)
                    cur = None
                if px is None:
                    if cur is not None:
                        self._cancel(ctx, m.ticker, side)
                    continue
                if cur is not None and cur.price == px:
                    continue  # keep our place in the queue
                if cur is not None:
                    self._cancel(ctx, m.ticker, side)
                s_ = Side.BUY if side == "bid" else Side.SELL
                room = self.p.max_pos - pos if side == "bid" else self.p.max_pos + pos
                qty = min(ctx.size(m.ticker, s_, px, tif=TIF.POST), room)
                if qty < 1:
                    continue
                fn = ctx.buy if side == "bid" else ctx.sell
                o = fn(m.ticker, px, qty, tif=TIF.POST, tag=side)
                if o is not None:
                    q[side] = o

    def on_settle(self, ctx, m, pnl):
        self.quotes.pop(m.ticker, None)
        self.flattened.discard(m.ticker)
        self.open_spot.pop(m.ticker, None)
        for side in ("bid", "ask"):
            self.pulled.pop((m.ticker, side), None)
