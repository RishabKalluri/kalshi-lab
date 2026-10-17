import pandas as pd, numpy as np
R="/srv/kalshi/strategies/pregame-maker/research/"
f=pd.read_parquet(R+"frame.parquet"); t=pd.read_parquet(R+"trades.parquet")
t=t.merge(f[["ticker","series","start","end","result"]],on="ticker")
t=t[(t.t>=t.start)&(t.t<t.end)].copy()      # in-game
t["y"]=(t.result=="yes").astype(float)
t["pay"]=np.where(t.side=="yes",t.p,1-t.p); t["win"]=np.where(t.side=="yes",t.y,1-t.y); t["edge"]=100*(t.win-t.pay)
t["pb"]=pd.cut(t.pay,[0,.06,.1,.9,.94,1.0]); t["sz"]=pd.cut(t.n,[0,20,100,1000,1e9])
for s,g in t.groupby("series"):
    print(s,"UNWEIGHTED per trade; mean edge c (n trades)")
    print(g.groupby(["pb","sz"],observed=True).edge.agg(["mean","size"]).round(2).unstack().to_string())
    print("per-event-clustered mean edge, fav side maker view = -edge for taker buying ≥0.9")
    ev=g.merge(f[["ticker","event"]],on="ticker")
    for lab,sel in (("taker pays .06-.1",(ev.pay>.06)&(ev.pay<=.1)),("taker pays .9-.94",(ev.pay>.9)&(ev.pay<=.94))):
        x=ev[sel].groupby("event").edge.mean()
        print(lab,"mean over events",round(x.mean(),2),"se",round(x.std()/np.sqrt(len(x)),2),"events",len(x))
