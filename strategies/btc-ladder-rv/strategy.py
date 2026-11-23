"""BTC range vs ladder relative value: trade Kalshi's thin hourly range markets (KXBTC, "between" strikes) against the
fair value implied by the liquid hourly above/below ladder (KXBTCD) of the same hour.

Both settle on the same 60 s BRTI average. For a range [lo, hi) the ladder implies
    fair = P(X > lo - 0.01) - P(X > hi),
with each P the ladder strike's mid (last provable bid / ask). A ladder mid counts only if its bid and ask were both
proved by taker prints within `max_age` seconds. When a range print proves a quote that is >= `edge` mills away from
fair (ask below fair: buy YES; bid above fair: sell YES), we take it with an IOC order and hold to settlement.
One entry per market. Research (Sep 22-29, trade prints, event-clustered): edge >= 8c nets +13c/ct (se 6, 153 hours).

History has trades but no books: the engine synthesizes the top of book from last trades, so a side is only traded on a
trade that proves that side's quote (taker BUY proves the ask, taker SELL the bid). No spot feed is needed.
Prices are YES mills.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000


class LadderRV(Strategy):
    params = {
        "edge": 80,         # mills between the proven range quote and ladder-implied fair
        "max_age": 60,      # seconds: both sides of a ladder strike must have printed this recently
        "min_ttc": 300,     # no entries in the last 5 minutes (ladder mids go stale while the average locks in)
        "max_spread": 400,  # skip stale/one-sided synthetic range books (ask - bid, mills)
        "lo_px": 20,
        "hi_px": 980,
    }

    def on_start(self, ctx):
        self.last = {}    # ladder ticker -> [t_buy, t_sell, p_ask, p_bid] (times in s)
        self.ladder = {}  # event -> {round(strike, 2): ticker}
        self.done = set()

    def _event(self, m):
        return (m.raw or {}).get("event_ticker", "").split("-", 1)[-1]

    def _mid(self, ctx, ev, strike, now_s):
        tk = self.ladder.get(ev, {}).get(round(strike, 2))
        if tk is None:
            return None
        rec = self.last.get(tk)
        if rec is None or rec[0] is None or rec[1] is None:
            return None
        if now_s - min(rec[0], rec[1]) > self.p.max_age:
            return None
        return (rec[2] + rec[3]) / 2

    def on_trade(self, ctx, tr):
        t = tr.ticker
        m = ctx.markets.get(t)
        if m is None or m.result is not None:
            return
        now_s = ctx.now // NS
        raw = m.raw or {}
        st, lo, hi = raw.get("strike_type"), raw.get("floor_strike"), raw.get("cap_strike")
        if m.series == "KXBTCD":
            if st == "greater" and lo is not None:
                self.ladder.setdefault(self._event(m), {})[round(lo, 2)] = t
                rec = self.last.setdefault(t, [None, None, 0, 0])
                book = ctx.book(t)
                if book is not None and book.best_bid is not None and book.best_ask is not None:
                    if tr.taker == Side.BUY:
                        rec[0], rec[2] = now_s, book.best_ask
                    else:
                        rec[1], rec[3] = now_s, book.best_bid
            return
        if m.series != "KXBTC" or st != "between" or lo is None or hi is None or t in self.done:
            return
        if ctx.seconds_left(t) < self.p.min_ttc:
            return
        book = ctx.book(t)
        if book is None or book.best_bid is None or book.best_ask is None:
            return
        bid, ask = book.best_bid, book.best_ask
        if ask - bid > self.p.max_spread:
            return
        ev = self._event(m)
        a, b = self._mid(ctx, ev, lo - 0.01, now_s), self._mid(ctx, ev, hi, now_s)
        if a is None or b is None:
            return
        fair = min(max(a - b, 0), 1000)
        if tr.taker == Side.BUY and fair - ask >= self.p.edge and self.p.lo_px <= ask <= self.p.hi_px:
            qty = ctx.size(t, Side.BUY, ask, tif=TIF.IOC)
            if qty >= 1 and ctx.buy(t, ask, qty, tif=TIF.IOC, tag="range-cheap") is not None:
                self.done.add(t)
        elif tr.taker == Side.SELL and bid - fair >= self.p.edge and self.p.lo_px <= bid <= self.p.hi_px:
            qty = ctx.size(t, Side.SELL, bid, tif=TIF.IOC)
            if qty >= 1 and ctx.sell(t, bid, qty, tif=TIF.IOC, tag="range-rich") is not None:
                self.done.add(t)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
