"""Taker/maker edge at price extremes by game phase (pre/in/post), outcome-based, from trades."""
import pandas as pd, numpy as np
R="/srv/kalshi/strategies/pregame-maker/research/"
f=pd.read_parquet(R+"frame.parquet"); t=pd.read_parquet(R+"trades.parquet")
t=t.merge(f[["ticker","series","start","end","result"]],on="ticker")
t["phase"]=np.where(t.t<t.start,"pre",np.where(t.t<t.end,"in","post"))
t["y"]=(t.result=="yes").astype(float)
# favourite-side view: price of the side bought; buyer of yes pays p, buyer of no pays 1-p
t["pay"]=np.where(t.side=="yes",t.p,1-t.p); t["win"]=np.where(t.side=="yes",t.y,1-t.y)
t["edge"]=t.win-t.pay
t["pb"]=pd.cut(t.pay,[0,.03,.06,.1,.9,.94,.97,.99,1.0])
def agg(x):
    n=x.n.sum(); return pd.Series(dict(ctr=n,trades=len(x),pay=(x.pay*x.n).sum()/n,win=(x.win*x.n).sum()/n,edge_c=100*(x.edge*x.n).sum()/n,mkts=x.ticker.nunique()))
for s,g in t.groupby("series"):
    print(s); print(g.groupby(["phase","pb"],observed=True).apply(agg).round(3).to_string())
