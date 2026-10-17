"""The rain-no rule (first taker-sell trade at YES price 10-90c, 0.5-6 h before expected expiration; buy NO) on other series. Screening."""
import sys, numpy as np, pandas as pd
D = sys.argv[1]
for s in sys.argv[2:]:
    df = pd.read_parquet(f"{D}/{s}.parquet", columns=["t", "p", "yes", "edge", "paid", "event", "market", "exp_ns", "close_ns"])
    ref = df.close_ns if s in ("KXRAIN",) or s.startswith("KXHIGH") or s.startswith("KXLOW") else df.exp_ns
    df["ttc"] = (ref - df.t) / 3.6e12
    won = (df.edge / 100 + df.paid).round()
    df["yes_out"] = np.where(df.yes, won, 1 - won)
    d = df[(~df.yes) & (df.ttc >= .5) & (df.ttc <= 6) & (df.p >= .1) & (df.p <= .9)].sort_values("t").groupby("market").head(1)
    if len(d) < 20:
        print(f"{s:22s} n={len(d)}"); continue
    pnl = 100 * ((1 - d.yes_out) - (1 - d.p))       # buy NO at the YES bid
    ev = pnl.groupby(d.event).mean()
    boots = [np.random.default_rng(i).choice(ev.values, len(ev)).mean() for i in range(500)]
    print(f"{s:22s} markets {len(d):5d} events {len(ev):5d} mean {pnl.mean():6.2f}c  event-mean {ev.mean():6.2f} CI [{np.percentile(boots,2.5):6.1f},{np.percentile(boots,97.5):6.1f}]  rain {d.yes_out.mean():.2f} avg yes bid {d.p.mean():.2f}")
