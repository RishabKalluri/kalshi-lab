"""Pre-game heavy favourites: price ~20 min before the estimated start vs outcome. NBA/NHL, by half."""
import pandas as pd, numpy as np
R="/srv/kalshi/strategies/pregame-maker/research/"
f=pd.read_parquet(R+"frame.parquet"); t=pd.read_parquet(R+"trades.parquet")
t=t.merge(f[["ticker","series","start","result"]],on="ticker")
t["h"]=(t.start-t.t)/3.6e12
rows=[]
for off in (0.25,1.0,3.0):
    w=t[(t.h>off)&(t.h<off+0.5)]
    p=w.groupby("ticker").apply(lambda x:(x.p*x.n).sum()/x.n.sum()).rename("p")
    d=f.set_index("ticker").join(p,how="inner")
    d["off"]=off; rows.append(d.reset_index())
d=pd.concat(rows)
d["y"]=(d.result=="yes").astype(float)
d["month"]=pd.to_datetime(d.start,unit="ns").dt.strftime("%m")
d["pb"]=pd.cut(d.p,[0,.05,.1,.15,.85,.9,.95,1])
def a(x):
    return pd.Series(dict(n=len(x),events=x.event.nunique(),p=x.p.mean(),win=x.y.mean(),edge_c=100*(x.y-x.p).mean()))
for s,g in d.groupby("series"):
    print(s); print(g.groupby(["off","pb"],observed=True).apply(a).round(3).to_string())
g=d[(d.series=="KXNBAGAME")&(d.off==0.25)&(d.p>=.88)]
print("NBA fav>=.88 at T-15..45m by month"); print(g.groupby("month").apply(a).round(3))
g=d[(d.series=="KXNBAGAME")&(d.off==0.25)&(d.p<=.12)]
print("NBA dog<=.12"); print(g.groupby("month").apply(a).round(3))
