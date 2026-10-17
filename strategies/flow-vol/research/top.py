"""Top-30% of s (market vol high vs forecast): favourite PnL at next fill, HAR vs HAR+flow, by month; with SE."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "strategies/flow-vol/research")
from r2 import load, GROUPS
from pnl_lib import wf
ALL = sum(GROUPS.values(), [])
fee = lambda p: np.ceil(7 * p * (1 - p)) / 100
for series in sys.argv[1:]:
    d = load(series); d["l5"] = np.log(d.rv_5m)
    d["pHAR"] = wf(d, []); d["pFLOW"] = wf(d, ["l5"] + ALL)
    d = d[d.close >= "2026-03-01"].dropna(subset=["iv", "pHAR", "pFLOW"]); d = d[d.iv > 0]
    yes = d.mid >= 0.5
    px = np.where(yes, d.next_ask, 1 - d.next_bid); win = np.where(yes, d.y == 1, d.y == 0)
    d["px"] = px; d["pnl"] = (win - px - fee(px)) * 100
    d = d[d.px.between(.55, .92) & d.h.isin([60, 90, 120, 180, 240, 300, 360])].dropna(subset=["pnl"])
    d["liv"] = np.log(d.iv); d["m"] = d.close.dt.strftime("%m")
    for name in ["pHAR", "pFLOW"]:
        s = d.liv - d[name]; q = s.quantile(.7); t = d[s > q]
        # one trade per market-ish: dedupe by ticker, first row
        t1 = t.sort_values("h", ascending=False).drop_duplicates("ticker")
        print(series, name, "rows", len(t), "mean %.2f se %.2f" % (t.pnl.mean(), t.pnl.std() / len(t) ** .5),
              "| 1/market n=%d mean %.2f se %.2f" % (len(t1), t1.pnl.mean(), t1.pnl.std() / len(t1) ** .5))
        print("   by month", t.groupby("m").pnl.mean().round(2).to_dict())
    s1 = d.liv - d.pHAR; s2 = d.liv - d.pFLOW
    both = d[(s1 > s1.quantile(.7)) & (s2 > s2.quantile(.7))]; only_f = d[(s2 > s2.quantile(.7)) & ~(s1 > s1.quantile(.7))]; only_h = d[(s1 > s1.quantile(.7)) & ~(s2 > s2.quantile(.7))]
    for n, x in [("both", both), ("flow-only", only_f), ("har-only", only_h)]:
        print("  ", n, len(x), round(x.pnl.mean(), 2), "se", round(x.pnl.std() / max(len(x), 1) ** .5, 2))
    print(series, "threshold sweep (flow model), rows / mean / se / months>0")
    for pq in (.5, .7, .8, .9, .95):
        s = d.liv - d.pFLOW; t = d[s > s.quantile(pq)]; mm = t.groupby("m").pnl.mean()
        print("  ", pq, len(t), round(t.pnl.mean(), 2), round(t.pnl.std() / len(t) ** .5, 2), (mm > 0).sum(), "/", len(mm))
