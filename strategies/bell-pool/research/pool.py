"""Opportunities + pooled underdog PnL for the two scheduled TradFi bells (NYSE 9:30 ET weekdays; Sunday 18:00 ET),
first qualifying checkpoint per market (h 240-600, underdog 10-45c, spread<=6c if known), after fee, next real fill.
Development data only. Prints per coin x bell: markets/month, mean, se, halves."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "strategies/bell-vol/research")
sys.path.insert(0, "strategies/us-hours-vol/strategy_dir")
from opens import load
HOL = {"2025-12-25","2026-01-01","2026-01-19","2026-02-16","2026-04-03","2026-05-25","2026-06-19","2026-07-03"}
rows = []
for s in sys.argv[1:] or ["KXETH15M", "KXBTC15M", "KXSOL15M"]:
    d = load(s)
    loc = d.start.dt.tz_convert("America/New_York")
    d["q"] = loc.dt.strftime("%H:%M"); d["dow"] = loc.dt.dayofweek; d["date"] = loc.dt.strftime("%Y-%m-%d")
    d["dmid"] = np.minimum(d.mid, 1 - d.mid)
    spr = (d.next_ask - d.next_bid) if "next_ask" in d else None
    b = d[d.dmid.between(0.10, 0.45) & d.next_ask.notna() & d.next_bid.notna() & d.h.between(240, 600)]
    bells = {"nyse0930": b[(b.q == "09:30") & (b.dow < 5) & ~b.date.isin(HOL)],
             "sun1800": b[(b.q == "18:00") & (b.dow == 6)]}
    for k, x in bells.items():
        pm = x.sort_values("h", ascending=False).groupby("ticker").first()
        pm["series"] = s; pm["bell"] = k
        rows.append(pm)
r = pd.concat(rows)
r["month"] = r.close.dt.strftime("%Y-%m")
def summ(x):
    se = x.dog.std() / max(1, len(x)) ** .5
    return f"n={len(x):4d} mean {x.dog.mean():+6.2f} se {se:5.2f}  A {x[x.half=='A'].dog.mean():+6.1f}({(x.half=='A').sum()}) B {x[x.half=='B'].dog.mean():+6.1f}({(x.half=='B').sum()})"
for (s, k), x in r.groupby(["series", "bell"]): print(s, k, summ(x))
for name, sel in [("ETH both", r.series == "KXETH15M"), ("ETH+BTC both", r.series.isin(["KXETH15M", "KXBTC15M"])),
                  ("ETH+BTC+SOL both", r.series != "x")]:
    x = r[sel]; print(name, summ(x), " months positive:", (x.groupby("month").dog.mean() > 0).sum(), "/", x.month.nunique())
    print("   per month n:", x.groupby("month").size().to_dict())
