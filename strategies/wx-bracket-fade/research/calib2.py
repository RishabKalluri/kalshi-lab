import pandas as pd, numpy as np
from sklearn.linear_model import LogisticRegression
d = pd.read_parquet("strategies/wx-bracket-fade/research/snaps_model.parquet")
d = d[d.last.notna() & (d.last_age < 90) & d.ask.notna() & d.bid.notna()].copy()
d["mid"] = (d.ask + d.bid) / 2
d["b"] = pd.cut(d.mid, [0, .05, .1, .2, .3, .4, .5, .6, .7, .8, .9, 1])
print(d.groupby("b", observed=True).agg(n=("y", "size"), freq=("y", "mean"), mid=("mid", "mean"), model=("pm", "mean")).round(3))
print("spread", (d.ask - d.bid).describe())
lg = lambda p: np.log(np.clip(p, .01, .99) / (1 - np.clip(p, .01, .99)))
X = pd.DataFrame({"mid": lg(d.mid), "model": lg(d.pm)})
m = LogisticRegression(C=1e6).fit(X, d.y); print("coef", m.coef_, m.intercept_)
