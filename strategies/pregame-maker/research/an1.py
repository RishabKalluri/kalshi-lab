import pandas as pd, numpy as np
R="/srv/kalshi/strategies/pregame-maker/research/"
f=pd.read_parquet(R+"frame.parquet"); t=pd.read_parquet(R+"trades.parquet")
t=t.merge(f[["ticker","series","start","result"]],on="ticker")
t["mins"]=(t.start-t.t)/6e10   # minutes before start (positive = pre-game)
pre=t[(t.mins>0)&(t.mins<24*60)].copy()
pre["y"]=(pre.result=="yes").astype(float)
# taker edge: buy yes at p -> y-p ; taker no -> (1-y)-(1-p)=p-y
pre["edge"]=np.where(pre.side=="yes",pre.y-pre.p,pre.p-pre.y)
print(f.groupby("series").size(), f.result.value_counts())
for s,g in pre.groupby("series"):
    print(s,"pre trades",len(g),"contracts",g.n.sum(),"per market contracts",g.n.sum()/g.ticker.nunique())
    for lo,hi in [(0,15),(15,60),(60,180),(180,720),(720,1440)]:
        h=g[(g.mins>lo)&(g.mins<=hi)]
        print(f"  {lo}-{hi}m  contracts/mkt {h.n.sum()/g.ticker.nunique():9.0f}  taker edge (cw) {100*(h.edge*h.n).sum()/h.n.sum():6.2f}c")
# timing of the schedule start vs expected expiration
f["exp_ns"]=pd.to_datetime(f.exp,utc=True).astype("int64")
print(((f.exp_ns-f.start)/3.6e12).groupby(f.series).describe())
