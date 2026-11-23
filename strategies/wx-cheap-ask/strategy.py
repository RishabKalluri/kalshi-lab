"""Weather maker: post-only quotes on Kalshi daily-high brackets, earning the spread retail pays.

Weather has no maker fees; takers lose 0.3-1.6c/contract against settlement (cheap brackets worst). Prices are about
right vs free forecasts (wx-bracket-fade found no taker edge), so the only money is the spread, net of adverse selection
when forecasts/observations move. v1: join the touch on brackets whose mid is in a band, only before a local-time
cutoff (the day's high is mostly locked by afternoon), pull a side after a fast mid move, and cap the exposure of each
city-day (all its brackets are one outcome).

Prices are YES mills. ctx.buy = bid for YES, ctx.sell = offer of YES (= buy NO).
"""

import re
from collections import deque
from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
TZ = {"KXHIGHNY": "America/New_York", "KXHIGHMIA": "America/New_York", "KXHIGHCHI": "America/Chicago",
      "KXHIGHAUS": "America/Chicago", "KXHIGHLAX": "America/Los_Angeles"}
MON = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}
TK = re.compile(r"-(\d\d)([A-Z]{3})(\d\d)-")


class WxMaker(Strategy):
    params = {
        "min_mid": 50,         # quote brackets with mid in [min_mid, max_mid] mills
        "max_mid": 500,
        "min_spread": 20,      # only quote when the touch spread is at least this many mills
        "sides": "both",       # both | bid | ask
        "cutoff_h": 13.0,      # stop quoting at this local hour on the market's day
        "pull_move": 30,       # pull a side when the mid moved this many mills within move_s
        "move_s": 600,
        "cooldown_s": 900,
        "cd_cap": 400,         # max contracts of exposure (sum |position|) per city-day
        "max_pos": 100,        # max |position| per bracket
        "back": 0,             # quote this many cents behind the touch (ask higher / bid lower)
        "qty": 10,             # contracts per quote (ctx.size is used if qty == 0)
    }

    def on_start(self, ctx):
        self.quotes = {}      # ticker -> {"bid": Order, "ask": Order}
        self.mids = {}        # ticker -> deque[(t, mid)]
        self.pulled = {}      # (ticker, side) -> until
        self.day_cache = {}   # ticker -> (series, day key, local midnight end ns)

    def _day(self, m):
        c = self.day_cache.get(m.ticker)
        if c is None:
            g = TK.search(m.ticker)
            tz = ZoneInfo(TZ.get(m.series, "America/New_York"))
            d = datetime(2000 + int(g[1]), MON[g[2]], int(g[3]), tzinfo=tz)
            c = (m.series + g.group(0), d.timestamp() * NS)
            self.day_cache[m.ticker] = c
        return c

    def _cancel(self, ctx, ticker, side):
        o = self.quotes.get(ticker, {}).pop(side, None)
        if o is not None and o.is_live:
            ctx.cancel(o)

    def on_timer(self, ctx):
        exposure = {}
        for m in ctx.markets.values():
            key, _ = self._day(m)
            exposure[key] = exposure.get(key, 0) + abs(ctx.position(m.ticker))
        for m in ctx.active_markets():
            book = ctx.book(m.ticker)
            if book is None or book.best_bid is None or book.best_ask is None:
                continue
            key, day0 = self._day(m)
            bid, ask = book.best_bid, book.best_ask
            mid = (bid + ask) / 2
            h = self.mids.setdefault(m.ticker, deque())
            h.append((ctx.now, mid))
            while len(h) > 1 and h[1][0] <= ctx.now - int(self.p.move_s * NS):
                h.popleft()
            move = mid - h[0][1]
            if move >= self.p.pull_move:       # YES jumped up: our offer is stale
                self.pulled[(m.ticker, "ask")] = ctx.now + int(self.p.cooldown_s * NS)
            elif move <= -self.p.pull_move:
                self.pulled[(m.ticker, "bid")] = ctx.now + int(self.p.cooldown_s * NS)
            local_h = (ctx.now - day0) / NS / 3600
            pos = ctx.position(m.ticker)
            ok = (local_h < self.p.cutoff_h and self.p.min_mid <= mid <= self.p.max_mid
                  and ask - bid >= self.p.min_spread)
            room_cd = self.p.cd_cap - exposure[key]
            want = {"bid": bid - 10 * self.p.back if ok and self.p.sides in ("both", "bid") and pos < self.p.max_pos else None,
                    "ask": ask + 10 * self.p.back if ok and self.p.sides in ("both", "ask") and pos > -self.p.max_pos else None}
            q = self.quotes.setdefault(m.ticker, {})
            for side, px in want.items():
                if self.pulled.get((m.ticker, side), 0) > ctx.now:
                    px = None
                cur = q.get(side)
                if cur is not None and not cur.is_live:
                    q.pop(side)
                    cur = None
                reduces = (side == "bid" and pos < 0) or (side == "ask" and pos > 0)
                if px is not None and room_cd < 1 and not reduces:
                    px = None
                if px is None:
                    if cur is not None:
                        self._cancel(ctx, m.ticker, side)
                    continue
                if cur is not None and cur.price == px:
                    continue  # keep queue position
                if cur is not None:
                    self._cancel(ctx, m.ticker, side)
                s_ = Side.BUY if side == "bid" else Side.SELL
                qty = self.p.qty or ctx.size(m.ticker, s_, px, tif=TIF.POST)
                if qty < 1:
                    continue
                o = (ctx.buy if side == "bid" else ctx.sell)(m.ticker, px, qty, tif=TIF.POST, tag=side)
                if o is not None:
                    q[side] = o

    def on_settle(self, ctx, m, pnl):
        self.quotes.pop(m.ticker, None)
        self.mids.pop(m.ticker, None)
        for side in ("bid", "ask"):
            self.pulled.pop((m.ticker, side), None)
