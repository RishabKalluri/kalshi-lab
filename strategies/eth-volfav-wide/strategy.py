"""ETH VolFavorite wide: eth-volfav2 with the entry bar lowered from the top 30% to the top 40% of implied/forecast
vol ratios (fit pct 0.7 -> 0.6). ETH VolFavorite v2: eth-volfav unchanged except realized vol is gap-safe (see _Hist) and paper runs a
re-measured rv_scale. Original docstring follows.

Buy the favorite when the market's implied vol is high relative to a vol forecast.

Research (research/vol_favorite_robust.py, 30 days, split by date): on KXETH15M, when
implied vol / forecast vol is in the top 20% (threshold fit on the first half), buying the side
priced above 50c between T-360s and T-60s earned +4.2c/contract after fees in the second half
(95% CI +1.7..+6.5c by market bootstrap, 13/15 days positive). The same test on BTC is negative:
the more competitive market prices vol correctly.

Mechanics, identical to the research:
  implied vol   iv = D / (Phi^-1(mid) * sqrt(tau - 40)),  D = spot + basis - strike, basis = strike -
                our 60s average before open (the strike is BRTI's 60s average before open)
  forecast      log rv = beta . [1, log rv15m, log rv60m, log rv4h, hour dummies, log tau]  (fit offline,
                strategies/eth-volfav/params/vol_model_<SERIES>.json via research/fit_vol_model.py)
  entry         ratio = iv / forecast > threshold  ->  buy the favorite at the ask (IOC)
"""

import json
import math
import os
import sys
import time
from pathlib import Path
from statistics import NormalDist

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
PARAMS = Path(__file__).parent / "params"
# Live/paper only: monthly refits (research/refit_live.py -> S3 -> `kalshi-lab models-pull`) land here and take
# precedence over params/; the trader re-reads the file when it changes, so a refit needs no restart.
LIVE_MODELS = (Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "models"
               / Path(__file__).parent.name)
_inv = NormalDist().inv_cdf


class _Hist:
    """1s spot samples for the last ~4h with a running sum of squared changes.

    A change across a gap of g seconds (live feed or recorder outage) is divided by g, so it adds one
    second's worth of variance instead of the whole gap's. v1 added the full squared jump, which inflated
    rv for up to 4h after any gap and suppressed trading. Backfill's 1s series has no gaps: unchanged there.
    """
    KEEP = 4 * 3600 + 120

    def __init__(self):
        self.secs, self.px, self.cum = [], [], [0.0]

    def add(self, sec, price):
        if self.px:
            gap = max(1, sec - self.secs[-1])
            self.cum.append(self.cum[-1] + (price - self.px[-1]) ** 2 / gap)
        self.secs.append(sec)
        self.px.append(price)
        if len(self.secs) > 2 * self.KEEP:  # trim in chunks so appends stay O(1) amortized
            k = len(self.secs) - self.KEEP
            self.secs, self.px = self.secs[k:], self.px[k:]
            base = self.cum[k]
            self.cum = [0.0] + [c - base for c in self.cum[k + 1:]]

    def window(self, a, b):
        import bisect
        i, j = bisect.bisect_left(self.secs, a), bisect.bisect_left(self.secs, b)
        return self.px[i:j]


class VolFavorite(Strategy):
    @classmethod
    def fit(cls, series: list[str], until: str | None) -> dict:
        """Pipeline hook: fit the vol model on data before `until`; returns param overrides."""
        from vol_fit import fit_model
        return {"model": fit_model(series[0], until, pct=0.6)}  # eth-volfav-wide: top 40% (v2: 0.7 = top 30%)

    params = {
        "model": "",           # params file name; default vol_model_<SERIES>.json
        "min_tau": 60,         # trade between min_tau and max_tau seconds before close
        "max_tau": 360,
        "cooldown_s": 0,       # seconds between entries in the same market (checkpoints are already >= 30s apart)
        "max_entries": 7,      # entries per market (research: 7 horizons)
        "threshold_mult": 1.0, # scale the fitted ratio threshold
        "min_hist_s": 3600,    # need this much spot history before trading (rv_4h falls back to what we have)
        # The model was fit on Binance 1s closes. The live multi-exchange median reads lower realized vol;
        # scale live rv onto the Binance scale (v1 used 1.09 from one partial day; re-measured in NOTES). 1.0 in backfill.
        "rv_scale": 1.0,
        # Evaluate only at these fixed horizons (seconds before close). Checking every second and entering
        # on the first crossing buys momentary jumps that reverse: engine walk-forward Apr/Jul/Sep went
        # from -0.2c/contract (every second) to +2.4..+8.2c (checkpoints). [] = every second.
        "checkpoints": [360, 300, 240, 180, 120, 90, 60],
        # IOC limit this many cents through the touch. On real books ~40% of at-the-touch IOCs missed because
        # the quote moved 1-5 ticks in the 150 ms latency (paper Oct 1); backfill's synthetic books never move.
        "slip_c": 0,
    }

    def on_start(self, ctx):
        self.hist: dict[str, deque] = {}     # series -> deque of (sec, spot), 1s samples, last 4h
        self.models: dict[str, dict] = {}
        self.basis: dict[str, float] = {}
        self.entries: dict[str, list[int]] = {}
        self.live = bool(ctx.spot_history)  # only live/paper engines provide spot history
        # Live/paper: preload the last 4h of spot from the recorder so there's no warm-up after a restart.
        if ctx.spot_history:
            for series in ctx.spot_map:
                pts = ctx.spot_history(series, 4 * 3600)
                h = self.hist.setdefault(series, _Hist())
                for sec, px in pts:
                    h.add(sec, px)
                ctx.log.info("VolFavorite: preloaded %d seconds of %s spot history", len(pts), series)

    def _model(self, series, ctx=None):
        name = self.p.model or f"vol_model_{series}.json"
        c = self.models.get(series)
        if c and (not self.live or time.monotonic() - c["checked"] < 300):
            return c["m"]
        path = LIVE_MODELS / name if self.live and not self.p.model and (LIVE_MODELS / name).exists() else PARAMS / name
        mtime = path.stat().st_mtime
        if not c or c["path"] != path or c["mtime"] != mtime:
            m = json.loads(path.read_text())
            if ctx is not None and self.live:
                ctx.log.info("VolFavorite: %s model %s (fit until %s, %s markets, threshold %.3f)", series, path,
                             m.get("fit_until"), m.get("n_markets"), m["ratio_threshold"])
            c = self.models[series] = dict(m=m, path=path, mtime=mtime)
        c["checked"] = time.monotonic()
        return c["m"]

    def _rv(self, h: "_Hist", window: int) -> float | None:
        """Realized vol ($/sqrt s) over the last `window` seconds of 1s samples, O(1) via running sums."""
        n = min(window, len(h.cum) - 1)
        if n < min(window, 300) // 2:
            return None
        return math.sqrt((h.cum[-1] - h.cum[-1 - n]) / n)

    def on_timer(self, ctx):
        now_s = ctx.now // NS
        for series in ctx.spot_map:
            s = ctx.spot(series=series)
            if s is None:
                continue
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
        if not (self.p.min_tau <= tau <= self.p.max_tau) or m.ticker not in self.basis:
            return
        if self.p.checkpoints and int(round(tau)) not in self.p.checkpoints:
            return
        ent = self.entries.setdefault(m.ticker, [])
        if len(ent) >= self.p.max_entries or (ent and now_s - ent[-1] < self.p.cooldown_s):
            return
        h = self.hist.get(m.series)
        book = ctx.book(m.ticker)
        if not h or book is None or book.best_bid is None or book.best_ask is None:
            return
        if h.secs[-1] - h.secs[0] < self.p.min_hist_s:
            return
        rv15, rv60 = self._rv(h, 900), self._rv(h, 3600)
        rv4h = self._rv(h, 14400) or rv60
        if not (rv15 and rv60 and rv4h):
            return
        rv15, rv60, rv4h = (x * self.p.rv_scale for x in (rv15, rv60, rv4h))
        mid = (book.best_bid + book.best_ask) / 2000
        if not (0.03 < mid < 0.97 and abs(mid - 0.5) > 0.07):
            return
        D = h.px[-1] + self.basis[m.ticker] - m.strike
        z = _inv(mid)
        if z * D <= 0:
            return  # spot and market disagree on the side: implied vol undefined
        iv = D / (z * math.sqrt(tau - 40))
        md = self._model(m.series, ctx)
        hour = (m.close_ts // NS // 3600) % 24
        x = [1.0, math.log(rv15), math.log(rv60), math.log(rv4h)] + [1.0 if hour == hh else 0.0 for hh in range(1, 24)] + [math.log(tau)]
        fc = math.exp(sum(b * v for b, v in zip(md["beta"], x)))
        ratio = iv / fc
        ctx.record(m.ticker, "ratio", ratio)
        if ratio <= md["ratio_threshold"] * self.p.threshold_mult:
            return
        if mid > 0.5:
            side, px = Side.BUY, book.best_ask
        else:
            side, px = Side.SELL, book.best_bid
        px = min(999, px + 10 * self.p.slip_c) if side == Side.BUY else max(1, px - 10 * self.p.slip_c)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"r={ratio:.2f}")
            ent.append(now_s)

    def on_settle(self, ctx, m, pnl):
        self.basis.pop(m.ticker, None)
        self.entries.pop(m.ticker, None)
