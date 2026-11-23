"""Rain NO on dry forecasts: rain-no's rule (buy NO at the YES bid late in the local day) only when the day-ahead model forecast
says no more rain is coming at that station.

Retail prices KXRAIN YES around 25-30% even when the forecast for the rest of the day is dry; in development those markets
resolved YES only 11-17% of the time, while markets with a wet remaining forecast were priced about right. The forecast is
Open-Meteo's `precipitation_previous_day1` (the run issued a day earlier, so no lookahead), stored in data/fc_<CITY>.csv
(hourly, UTC; the value at hour t is the precipitation over the hour ending at t).

Prices are YES mills. ctx.sell(YES) = buy NO. Entry: the first taker hit on the YES bid (it proves the bid) while the YES bid is in
[lo, hi], between min_ttc_h and max_ttc_h before the close, with remaining forecast precipitation <= max_mm; one entry per city-day.
"""

import datetime as dt
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from kalshi_lab.core.types import TIF, Side  # noqa: E402
from kalshi_lab.strategy import Strategy  # noqa: E402

NS = 1_000_000_000
HOUR = 3600 * NS
DATA = Path(__file__).parent / "data"


def _load(city):
    f = DATA / f"fc_{city}.csv"
    out = {}
    if not f.exists():
        return out
    for line in f.read_text().splitlines():
        p = line.split(",")
        if len(p) < 3 or p[0][:2] != "20":
            continue
        t = int(dt.datetime.fromisoformat(p[0]).replace(tzinfo=dt.timezone.utc).timestamp()) // 3600
        out[t] = (float(p[1] or 0), float(p[2] or 0))
    return out


class RainForecastNo(Strategy):
    params = {
        "lo": 100,          # YES bid window in mills
        "hi": 900,
        "min_ttc_h": 0.5,
        "max_ttc_h": 6.0,
        "max_spread": 300,
        "max_mm": 0.1,      # remaining forecast precipitation (mm) allowed
    }

    def on_start(self, ctx):
        self.done = set()
        self.fc = {}

    def _remaining_mm(self, city, now, close):
        if city not in self.fc:
            self.fc[city] = _load(city)
        f = self.fc[city]
        if not f:
            return None
        tot = 0.0
        for h in range(now // HOUR + 1, -(-close // HOUR) + 1):
            if h not in f:
                return None
            tot += f[h][0]
        return tot

    def on_trade(self, ctx, tr):
        m = ctx.markets.get(tr.ticker)
        if m is None or m.result is not None or tr.taker != Side.SELL:
            return  # only a taker hitting the bid proves where the (synthetic) bid is
        t = m.ticker
        if t in self.done:
            return
        h = ctx.seconds_left(t) / 3600
        if h > self.p.max_ttc_h or h < self.p.min_ttc_h:
            return
        book = ctx.book(t)
        if book is None or book.best_bid is None or book.best_ask is None:
            return
        bid, ask = book.best_bid, book.best_ask
        if not (self.p.lo <= bid <= self.p.hi) or ask - bid > self.p.max_spread:
            return
        rem = self._remaining_mm(t.rsplit("-", 1)[-1], ctx.now, m.close_ts)
        if rem is None or rem > self.p.max_mm:
            return
        qty = ctx.size(t, Side.SELL, bid, tif=TIF.IOC)
        if qty < 1:
            return
        if ctx.sell(t, bid, qty, tif=TIF.IOC, tag="no") is not None:
            self.done.add(t)

    def on_settle(self, ctx, m, pnl):
        self.done.discard(m.ticker)
