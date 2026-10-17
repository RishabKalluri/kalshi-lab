"""Screen (dev data only): KXTRUMPMENTION early price vs outcome. NO is bought by selling YES at the bid proven by a
taker-SELL trade (yes==False) at/after open+h hours. Input: parquet from strategies/nhl-quiet/research/screen.py."""
import sys, numpy as np, pandas as pd
d = pd.read_parquet(sys.argv[1])
won = (d.edge / 100 + d.paid).round()
d["out"] = np.where(d.yes, won, 1 - won)
d["p"] = np.where(d.yes, d.paid, 1 - d.paid)
rows = []
for mk, g in d.groupby("market"):
    g = g.sort_values("t"); o = g.out.iloc[0]; open_ = g.open_ns.iloc[0]
    for h in (0, 1, 3):
        s = g[(g.t >= g.t.iloc[0] + h * 3.6e12) & (~g.yes)]       # taker sold YES => bid proven
        if len(s): rows.append((mk, g.event.iloc[0], h, s.p.iloc[0], o, s.t.iloc[0], s.c.iloc[0]))
r = pd.DataFrame(rows, columns=["m", "ev", "h", "bid", "out", "t", "c"])
r["fee"] = 0.07 * r.bid * (1 - r.bid)
r["pnl"] = (r.bid - r.out - r.fee) * 100            # sell YES at bid (= buy NO at 1-bid), net of taker fee
r["half"] = (r.t > r.t.median()).astype(int)
for h in (0, 1, 3):
    for lo, hi in ((.1, .9), (.2, .8), (.3, .7), (.1, .3), (.3, .5), (.5, .7), (.7, .9)):
        z = r[(r.h == h) & (r.bid > lo) & (r.bid <= hi)]
        if len(z) < 8: continue
        a = [z[z.half == k].pnl.mean() for k in (0, 1)]
        print(f"h{h} bid {lo}-{hi}: n={len(z)} net {z.pnl.mean():5.1f}c se {z.pnl.std()/np.sqrt(len(z)):4.1f}  halves {a[0]:5.1f} {a[1]:5.1f}")
