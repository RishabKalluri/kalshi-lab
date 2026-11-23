"""SOL early-window spread maker: join the best bid and best ask early in each window, hold fills to settlement.

Screen (trade table, dev data): the counterparty of every taker print at 15-85c earns +1.2c/ct gross when the print is in the first
5 minutes (600-900 s left), +0.6c overall; makers pay no fee. Adverse selection is the unknown, so the engine decides.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class SpreadMaker(Strategy):
    params = {"start_s": 5, "stop_tau": 600, "lo": 300, "hi": 700, "min_spread": 20, "ttl_s": 20, "max_pos": 3, "calm_bp": 0.0, "min_hist": 10, "fav_only": 0}

    def on_start(self, ctx):
        self.q = {}  # ticker -> (bid_order, ask_order, t0)
        self.sp = []

    def on_timer(self, ctx):
        now = ctx.now
        sp = ctx.spot(series='KXSOL15M')
        if sp is not None:
            self.sp.append((now // NS, sp)); self.sp = self.sp[-60:]
        calm = True
        if self.p.calm_bp > 0:
            old = [x for t, x in self.sp if t <= now // NS - self.p.min_hist]
            calm = bool(old) and abs(sp / old[-1] - 1) * 1e4 <= self.p.calm_bp
        for m in ctx.active_markets():
            tau = (m.close_ts - now) / NS
            age = (now - m.open_ts) / NS
            tk = m.ticker
            cur = self.q.get(tk)
            if cur:
                if not calm or tau < self.p.stop_tau or now / NS - cur[2] >= self.p.ttl_s:
                    ctx.cancel_all(tk)
                    self.q.pop(tk)
                    cur = None
                else:
                    continue
            if not calm or age < self.p.start_s or tau < self.p.stop_tau:
                continue
            book = ctx.book(tk)
            if book is None or book.best_bid is None or book.best_ask is None:
                continue
            bb, ba = book.best_bid, book.best_ask
            mid = (bb + ba) / 2
            if self.p.fav_only:
                fm = max(mid, 1000 - mid)
                if not (self.p.lo <= fm <= self.p.hi) or ba - bb < self.p.min_spread:
                    continue
            elif not (self.p.lo <= mid <= self.p.hi) or ba - bb < self.p.min_spread:
                continue
            pos = ctx.position(tk)
            if abs(pos) >= self.p.max_pos * 1:
                pass
            qb = ctx.size(tk, Side.BUY, bb, tif=TIF.POST)
            qa = ctx.size(tk, Side.SELL, ba, tif=TIF.POST)
            if self.p.fav_only:
                if mid >= 500:
                    qa = 0
                else:
                    qb = 0
            ob = ctx.buy(tk, bb, qb, tif=TIF.POST, tag="bid") if qb >= 1 else None
            oa = ctx.sell(tk, ba, qa, tif=TIF.POST, tag="ask") if qa >= 1 else None
            self.q[tk] = (ob, oa, now / NS)

    def on_settle(self, ctx, m, pnl):
        self.q.pop(m.ticker, None)
