import pandas as pd, numpy as np
R="/srv/kalshi/strategies/pregame-maker/research/"
f=pd.read_parquet(R+"frame.parquet"); t=pd.read_parquet(R+"trades.parquet")
t=t.merge(f[["ticker","series","start","result","open"]],on="ticker")
t["h"]=(t.start-t.t)/3.6e12
ref=t[(t.h>0.25)&(t.h<0.75)].groupby("ticker").apply(lambda x:(x.p*x.n).sum()/x.n.sum()).rename("ref")
pre=t[(t.h>0.75)&(t.h<96)].join(ref,on="ticker").dropna(subset=["ref"]).copy()
pre["y"]=(pre.result=="yes").astype(float)
pre["mk"]=np.where(pre.side=="yes",pre.ref-pre.p,pre.p-pre.ref)    # markout vs pre-game ref (no outcome noise)
pre["edge"]=np.where(pre.side=="yes",pre.y-pre.p,pre.p-pre.y)
pre["bin"]=pd.cut(pre.h,[0.75,3,6,12,24,36,48,60,72,96])
for s,g in pre.groupby("series"):
    a=g.groupby("bin",observed=True).apply(lambda x: pd.Series(dict(ctr=x.n.sum(),mk_c=100*(x.mk*x.n).sum()/x.n.sum(),edge_c=100*(x.edge*x.n).sum()/x.n.sum(),mk_med=100*x.mk.median())))
    print(s);print(a.round(2))
# time since open
pre["since_open_h"]=(pre.t-pd.to_datetime(pre.open,utc=True,format="ISO8601").astype("int64").values.astype(float)*0+0)
