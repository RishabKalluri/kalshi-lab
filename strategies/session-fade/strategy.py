"""Post-fixing reversal: fade the NY session's BTC move in the 15-minute window that opens at 16:00 ET.

From 09:30 to 16:00 ET the US session's flow (spot-ETF creations/redemptions filled into the 15:00-16:00 ET CF
fixing, CME settlement at 16:00 ET, equity-hedged books trading with the cash session) pushes BTC in the session's
direction. At 16:00 that pressure stops and part of it reverts within 15 minutes. Research on dev data
(research/screen_h2.py, h3_coins.py): corr(session return, 16:00-16:15 window return) = -0.36 / -0.33 (Dec-Apr /
May-Aug) on BTC, -0.34/-0.38 ETH, -0.27/-0.46 SOL; the Kalshi 16:00 window opens near 50/50 regardless, and fading
at the next real fill made about +11c/contract after fee in both halves.

  R = (S(open) - S(09:30 ET)) / (rv_60m * sqrt(seconds since 09:30)),  rv_60m from 1 s spot changes
  only the window opening at `slot` ET on NYSE full trading days (no weekends, holidays, early closes)
  entry at fixed checkpoints h = 870/840/810/780 s, once per market: |R| > r_thr, mid within [lo, hi]
        -> buy the side that bets against the session's move, at the touch (IOC, slip_c cents through). Hold.
"""

import bisect
import math
import sys
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
NY = ZoneInfo("America/New_York")
# NYSE full-day holidays and 13:00 early closes (no 16:00 close / fixing), 2025-2026.
NO_SESSION = {
    "2025-11-27", "2025-11-28", "2025-12-24", "2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03",
    "2026-05-25", "2026-06-19", "2026-07-03", "2026-09-07", "2026-11-26", "2026-11-27", "2026-12-24", "2026-12-25",
}


class _Hist:
    """1 s spot samples (last ~8 h) with running sums of squared changes."""
    KEEP = 8 * 3600

    def __init__(self):
        self.secs, self.px, self.cum = [], [], [0.0]

    def add(self, sec, price):
        if self.secs and sec <= self.secs[-1]:
            return
        if self.px:
            self.cum.append(self.cum[-1] + (price - self.px[-1]) ** 2)
        self.secs.append(sec)
        self.px.append(price)
        if len(self.secs) > 2 * self.KEEP:
            k = len(self.secs) - self.KEEP
            self.secs, self.px = self.secs[k:], self.px[k:]
            b = self.cum[k]
            self.cum = [0.0] + [c - b for c in self.cum[k + 1:]]

    def rv_before(self, sec, window):
        """Per-second dollar vol over [sec - window, sec)."""
        j = bisect.bisect_left(self.secs, sec)
        i = bisect.bisect_left(self.secs, sec - window)
        if j - i < window // 2 or j < 1:
            return None
        return math.sqrt((self.cum[j - 1] - self.cum[max(i - 1, 0)]) / (j - i))

    def at(self, sec, tol=30):
        """First sample at or after sec (within tol seconds)."""
        i = bisect.bisect_left(self.secs, sec)
        if i < len(self.secs) and self.secs[i] - sec <= tol:
            return self.px[i]
        return None


class SessionFade(Strategy):
    params = {
        "slot": "16:00",                       # ET open time of the window traded
        "session": "09:30",                    # ET start of the session move
        "r_thr": 0.5,                          # |session move| in session sigmas
        "checkpoints": [870, 840, 810, 780],   # seconds before close; one entry per market at the first that fires
        "lo": 300, "hi": 700,                  # mid range (mills)
        "rv_scale": 1.0,                       # live multi-exchange median reads lower rv than Binance 1 s
        "slip_c": 0,                           # IOC this many cents through the touch (paper: 1)
    }

    def on_start(self, ctx):
        self.hist: dict[str, _Hist] = {}
        self.done: set[str] = set()
        if ctx.spot_history:
            for series in ctx.spot_map:
                h = self.hist.setdefault(series, _Hist())
                for sec, px in ctx.spot_history(series, 8 * 3600):
                    h.add(sec, px)

    def _session(self, open_s):
        """(session start ts) if this window opens at `slot` ET on a full NYSE trading day, else None."""
        dt = datetime.fromtimestamp(open_s, timezone.utc).astimezone(NY)
        if dt.strftime("%H:%M") != self.p.slot or dt.weekday() >= 5 or dt.strftime("%Y-%m-%d") in NO_SESSION:
            return None
        hh, mm = (int(x) for x in self.p.session.split(":"))
        return int(dt.replace(hour=hh, minute=mm, second=0).timestamp())

    def on_timer(self, ctx):
        now_s = ctx.now // NS
        for series in ctx.spot_map:
            s = ctx.spot(series=series)
            if s is not None:
                self.hist.setdefault(series, _Hist()).add(now_s, s)
        for m in ctx.active_markets():
            if m.ticker in self.done:
                continue
            tau = int(round((m.close_ts - ctx.now) / NS))
            if tau < min(self.p.checkpoints):
                self.done.add(m.ticker)
                continue
            if tau in self.p.checkpoints:
                self._consider(ctx, m)

    def _consider(self, ctx, m):
        op = m.open_ts // NS
        start = self._session(op)
        if start is None:
            self.done.add(m.ticker)
            return
        h = self.hist.get(m.series)
        if not h:
            return
        s0, s1, rv = h.at(start), h.at(op), h.rv_before(op, 3600)
        if s0 is None or s1 is None or not rv:
            return
        R = (s1 - s0) / (rv * self.p.rv_scale * math.sqrt(op - start))
        ctx.record(m.ticker, "session_R", R)
        if abs(R) <= self.p.r_thr:
            self.done.add(m.ticker)
            return
        book = ctx.book(m.ticker)
        if book is None or book.best_bid is None or book.best_ask is None or book.best_ask < book.best_bid:
            return
        mid = (book.best_bid + book.best_ask) / 2
        if not (self.p.lo <= mid <= self.p.hi):
            return
        if R < 0:
            side, px = Side.BUY, min(999, book.best_ask + 10 * self.p.slip_c)
        else:
            side, px = Side.SELL, max(1, book.best_bid - 10 * self.p.slip_c)
        qty = ctx.size(m.ticker, side, px, tif=TIF.IOC)
        if qty >= 1:
            (ctx.buy if side == Side.BUY else ctx.sell)(m.ticker, px, qty, tif=TIF.IOC, tag=f"R={R:+.2f}")
            self.done.add(m.ticker)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
