import pandas as pd, numpy as np
R="/srv/kalshi/strategies/pregame-maker/research/"
f=pd.read_parquet(R+"frame.parquet"); t=pd.read_parquet(R+"trades.parquet")
t=t.merge(f[["ticker","series","start","result"]],on="ticker")
t["h"]=(t.start-t.t)/3.6e12
pre=t[(t.h>0)&(t.h<96)].copy()
pre["y"]=(pre.result=="yes").astype(float)
pre["edge"]=np.where(pre.side=="yes",pre.y-pre.p,pre.p-pre.y)
pre["bin"]=pd.cut(pre.h,[0,1,3,6,12,24,48,72,96])
nm=f.groupby("series").size()
for s,g in pre.groupby("series"):
    a=g.groupby("bin",observed=True).apply(lambda x: pd.Series(dict(ctr_per_mkt=x.n.sum()/nm[s],trades_per_mkt=len(x)/nm[s],edge_c=100*(x.edge*x.n).sum()/x.n.sum(),avgsize=x.n.mean())))
    print(s);print(a.round(2))
