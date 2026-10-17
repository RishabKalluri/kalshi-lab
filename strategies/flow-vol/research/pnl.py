"""Does the flow forecast beat the market's implied vol? Walk-forward (monthly refit on earlier data, Mar-Aug) predictions;
signal s = log(iv) - log(forecast). Side PnL at the next real taker fill after fee, by decile of s, for HAR vs HAR+flow.
Also: regression of log rv_fut on log iv + HAR + flow (does flow carry info beyond the market's iv?)."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, "strategies/flow-vol/research")
from r2 import load, GROUPS, fitpred, HAR
pd.set_option("display.width", 220)
fee = lambda p: np.ceil(7 * p * (1 - p)) / 100
ALL = sum(GROUPS.values(), [])


def wf(d, cols):
    out = pd.Series(np.nan, index=d.index)
    for m in pd.period_range("2026-03", "2026-08", freq="M"):
        s, e = m.start_time.tz_localize("UTC"), (m + 1).start_time.tz_localize("UTC")
        a = d[(d.close < s) & (d.rv_fut > 0.0)]; b = d[(d.close >= s) & (d.close < e)]
        out[b.index] = fitpred(a, b, cols)
    return out


for series in sys.argv[1:]:
    d = load(series)
    d["l5"] = np.log(d.rv_5m)
    d = d[d.close >= "2026-03-01"].copy() if False else d
    d["pHAR"] = wf(d, [])
    d["pFLOW"] = wf(d, ["l5"] + ALL)
    d = d[d.close >= "2026-03-01"].dropna(subset=["iv", "pHAR", "pFLOW"]).copy()
    d = d[(d.iv > 0)]
    d["liv"] = np.log(d.iv)
    d["dog_yes"] = d.mid < 0.5
    for side in ("fav", "dog"):
        yes = (d.mid >= 0.5) if side == "fav" else (d.mid < 0.5)
        px = np.where(yes, d.next_ask, 1 - d.next_bid)
        win = np.where(yes, d.y == 1, d.y == 0)
        d[f"{side}_px"] = px
        d[f"{side}_pnl"] = (win - px - fee(px)) * 100
    d["half"] = np.where(d.close < "2026-06-01", "Mar-May", "Jun-Aug")
    # info beyond iv
    for tag, extra in [("HAR", []), ("flow", ["l5"] + ALL)]:
        X = np.column_stack([HAR(d), d.liv] + [d[c] for c in extra])
        y = np.log(d.rv_fut)
    print(series, "rows", len(d))
    # corr of residual: (log rv_fut - log iv) vs (pFLOW - pHAR)
    resid = np.log(d.rv_fut) - d.liv
    print(" corr(log rv_fut - log iv, pHAR - log iv)  =", round(np.corrcoef(resid, d.pHAR - d.liv)[0, 1], 4),
          "  corr(.., pFLOW - log iv) =", round(np.corrcoef(resid, d.pFLOW - d.liv)[0, 1], 4),
          "  corr(.., pFLOW - pHAR) =", round(np.corrcoef(resid, d.pFLOW - d.pHAR)[0, 1], 4))
    for name in ["pHAR", "pFLOW"]:
        d["s"] = d.liv - d[name]
        for side, lo, hi in [("fav", .55, .92), ("dog", .08, .45)]:
            q = d[(d[f"{side}_px"].between(lo, hi)) & d.h.isin([60, 90, 120, 180, 240, 300, 360])].dropna(subset=[f"{side}_pnl"]).copy()
            q["dec"] = pd.qcut(q.s, 10, labels=False)
            t = q.groupby(["dec", "half"])[f"{side}_pnl"].mean().unstack()
            t["n"] = q.groupby("dec").size()
            t["all"] = q.groupby("dec")[f"{side}_pnl"].mean()
            print(f"\n{series} {name} {side} PnL c/ct by decile of log iv - log forecast (high=market vol too high)")
            print(t.round(2).T.to_string())
    # incremental: among rows where HAR says nothing (s_HAR decile mid), sort by pFLOW - pHAR
    d["dflow"] = d.pFLOW - d.pHAR
    for side, lo, hi in [("fav", .55, .92), ("dog", .08, .45)]:
        q = d[(d[f"{side}_px"].between(lo, hi)) & d.h.isin([60, 90, 120, 180, 240, 300, 360])].dropna(subset=[f"{side}_pnl"]).copy()
        q["dec"] = pd.qcut(q.dflow, 10, labels=False)
        t = q.groupby(["dec", "half"])[f"{side}_pnl"].mean().unstack(); t["all"] = q.groupby("dec")[f"{side}_pnl"].mean()
        print(f"\n{series} {side} PnL by decile of (flow forecast - HAR forecast), low = flow says calmer")
        print(t.round(2).T.to_string())
