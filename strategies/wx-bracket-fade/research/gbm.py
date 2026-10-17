import pandas as pd, numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import log_loss, brier_score_loss
d = pd.read_parquet("strategies/wx-bracket-fade/research/intraday.parquet")
d = d[d.ask.notna() & d.bid.notna() & (d.ask_age < 90) & (d.bid_age < 90)].copy()
d["mid"] = (d.ask + d.bid) / 2
lo = np.where(d.stype == "less", -99, d.floor); hi = np.where(d.stype == "greater", 199, d.cap)
d["dlo"] = d.M - lo; d["dhi"] = d.M - hi   # M relative to bracket edges
d["lm"] = np.log(d.mid.clip(.01, .99) / (1 - d.mid.clip(.01, .99)))
d["sp"] = d.ask - d.bid
F = ["lm", "dlo", "dhi", "h", "sp"]
tr, te = d[d.day < "2026-04-01"], d[d.day >= "2026-04-01"]
m = HistGradientBoostingClassifier(max_depth=4, learning_rate=.05, max_iter=200).fit(tr[F], tr.y)
p = m.predict_proba(te[F])[:, 1]
print(len(tr), len(te), "logloss mid", log_loss(te.y, te.mid.clip(.01, .99)), "gbm", log_loss(te.y, p.clip(.005, .995)))
te = te.assign(pg=p)
fee = lambda q: np.ceil(0.07 * q * (1 - q) * 100 - 1e-9) / 100
for mg in (.03, .05, .1):
    a = te[te.pg - te.ask > mg]; a = a.assign(pnl=a.y - a.ask - fee(a.ask))
    b = te[(1 - te.pg) - (1 - te.bid) > mg]; b = b.assign(pnl=(1 - b.y) - (1 - b.bid) - fee(1 - b.bid))
    print(mg, "YES", len(a), a.pnl.mean(), "NO", len(b), b.pnl.mean())
