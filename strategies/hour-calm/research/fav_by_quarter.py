"""Screen 2b: one trade per market. Rule fixed before looking: first checkpoint with h in [240, 720] where the
favourite's mid is 55-90c and a next real fill exists; buy the favourite at that fill, pay the taker fee, hold.
Per coin x window-start minute: mean c/ct, se, n; per month for the :45 (and :30) windows. Development only."""
import sys
import numpy as np, pandas as pd
sys.path.insert(0, "strategies/hour-calm/research")
from opens import load


def trades(s, side="fav", hlo=240, hhi=720):
    d = load(s)
    d["mn"] = d.start.dt.minute
    yes_fav = d.mid >= 0.5
    if side == "fav":
        px = np.where(yes_fav, d.next_ask, 1 - d.next_bid)
        win = np.where(yes_fav, d.y, 1 - d.y)
        fm = np.where(yes_fav, d.mid, 1 - d.mid)
    else:
        px = np.where(yes_fav, 1 - d.next_bid, d.next_ask)
        win = np.where(yes_fav, 1 - d.y, d.y)
        fm = np.where(yes_fav, d.mid, 1 - d.mid)
    d["px"], d["pnl"] = px, 100 * (win - px) - 7 * px * (1 - px)
    d["fm"] = fm
    x = d[d.h.between(hlo, hhi) & (d.fm >= 0.55) & (d.fm <= 0.90) & np.isfinite(d.px) & (d.px > 0)]
    x = x.sort_values("h", ascending=False).groupby("ticker").head(1)
    return x


if __name__ == "__main__":
    side = sys.argv[1] if len(sys.argv) > 1 else "fav"
    for s in ["KXETH15M", "KXSOL15M", "KXBTC15M"]:
        x = trades(s, side)
        g = x.groupby(["mn", "half"]).pnl.agg(["mean", "sem", "size"]).unstack("half")
        print(f"\n== {s} {side}: one trade per market")
        print(g.round(2).to_string())
        for mn in (30, 45):
            print(f"  :{mn} by month:", x[x.mn == mn].groupby("month").pnl.mean().round(1).to_dict())
        print("  other minutes by month:", x[x.mn.isin([0, 15])].groupby("month").pnl.mean().round(1).to_dict())
