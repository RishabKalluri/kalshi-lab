import pandas as pd, numpy as np
d = pd.read_parquet("strategies/wx-bracket-fade/research/intraday.parquet")
fee = lambda p: np.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100
def status(r, mg):
    M = r.M
    if r.stype == "greater": return "yes" if M >= r.floor + 1 + mg else None
    if r.stype == "less": return "no" if M >= r.cap + mg else None
    return "no" if M >= r.cap + 1 + mg else None
for mg in (0, 1, 2):
    d["lock"] = d.apply(lambda r: status(r, mg), axis=1)
    L = d[d.lock.notna()].copy()
    L["wrong"] = (L.lock == "yes") != (L.y == 1)
    yes = L[(L.lock == "yes") & L.ask.notna() & (L.ask_age < 60)].copy(); yes["pnl"] = 1 - yes.ask - fee(yes.ask)
    no = L[(L.lock == "no") & L.bid.notna() & (L.bid_age < 60)].copy(); no["pnl"] = 1 - (1 - no.bid) - fee(1 - no.bid)
    print("margin", mg, "locked", len(L), "wrong", L.wrong.sum(), "| YES n", len(yes), "pnl", yes.pnl.mean(), "ask mean", yes.ask.mean(),
          "| NO n", len(no), "pnl", no.pnl.mean(), "bid mean", no.bid.mean())
    print(yes.groupby("h").pnl.agg(["mean", "count"]).T.round(3).to_string())
    print(no.groupby("h").pnl.agg(["mean", "count"]).T.round(3).to_string())

print("--- any age")
d["lock"] = d.apply(lambda r: status(r, 1), axis=1)
L = d[d.lock.notna()]
yes = L[(L.lock == "yes") & L.ask.notna()].copy(); yes["pnl"] = 1 - yes.ask - fee(yes.ask)
no = L[(L.lock == "no") & L.bid.notna()].copy(); no["pnl"] = bid = no.bid - fee(1 - no.bid)  # NO pays 1, costs 1-bid
no["pnl"] = no.bid - fee(1 - no.bid)
print("YES", len(yes), yes.pnl.mean(), (yes.pnl > 0.02).sum(), " NO", len(no), no.pnl.mean(), (no.pnl > 0.02).sum())
print(yes.groupby("h").pnl.agg(["mean", "count"]).T.round(3).to_string()); print(no.groupby("h").pnl.agg(["mean", "count"]).T.round(3).to_string())
print(no[no.pnl > 0.02][["ticker","h","M","bid","bid_age","pnl"]].head(15))
