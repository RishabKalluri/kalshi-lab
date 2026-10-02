"""Screen 3: the 9:30 ET window (US equity open). Underdog at next real fill after fee, by horizon, mid bucket,
month; NYSE holidays as a placebo; the 10:00 window as a second slot. One row per market (first qualifying
horizon) for the per-market stats, to avoid counting the same market several times."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "strategies/us-hours-vol/research")
from iv_gap import load

HOL = {"2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03"}
if __name__ == "__main__":
    for s in sys.argv[1:] or ["KXETH15M", "KXSOL15M", "KXBTC15M"]:
        d = load(s)
        d["date"] = d.et.dt.strftime("%Y-%m-%d")
        d["hol"] = d.date.isin(HOL)
        d["dmid"] = np.minimum(d.mid, 1 - d.mid)
        base = d[d.dmid.between(0.10, 0.45) & d.next_ask.notna() & d.next_bid.notna()]
        print(f"\n===== {s}")
        for slot in ["09:30", "10:00", "09:15", "09:45"]:
            x = base[(base.q == slot) & ~base.wkend & ~base.hol]
            print(f"-- slot {slot}: dog pnl by h (A | B)  [all-slot weekday baseline in brackets]")
            allw = base[~base.wkend]
            r = []
            for h in sorted(x.h.unique(), reverse=True):
                a, b = x[(x.h == h) & (x.half == "A")].dog, x[(x.h == h) & (x.half == "B")].dog
                ba = allw[allw.h == h].dog.mean()
                r.append(f"h{h}: {a.mean():+.1f}|{b.mean():+.1f} n{len(a)}/{len(b)} [{ba:+.1f}]")
            print("  " + "\n  ".join(r))
        x = base[(base.q == "09:30") & ~base.wkend & ~base.hol & base.h.between(240, 600)]
        pm = x.sort_values("h", ascending=False).groupby("ticker").first()  # first checkpoint per market
        print("-- 09:30, h240-600, first checkpoint per market: n=%d mean %+.2f c, se %.2f" % (len(pm), pm.dog.mean(), pm.dog.std() / np.sqrt(len(pm))))
        print("   by month:", pm.groupby(pm.close.dt.strftime("%m")).dog.agg(lambda v: f"{v.mean():+.1f}({len(v)})").to_dict())
        print("   by dog price:", pm.groupby(pd.cut(pm.dmid, [0.1, 0.2, 0.3, 0.45])).dog.agg(lambda v: f"{v.mean():+.1f}({len(v)})").to_dict())
        xh = base[(base.q == "09:30") & base.hol & base.h.between(240, 600)]
        print("   holidays placebo rows: n=%d mean %+.1f ; weekends 09:30: %+.1f (n=%d)" % (
            len(xh), xh.dog.mean(), base[(base.q == "09:30") & base.wkend & base.h.between(240, 600)].dog.mean(),
            len(base[(base.q == "09:30") & base.wkend & base.h.between(240, 600)])))
