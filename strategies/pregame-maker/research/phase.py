"""Phase decomposition of backtest fills: pre-game / in-game quarter of the game / after the final whistle."""
import sys, json
import numpy as np, pandas as pd
sched = json.load(open("/srv/kalshi/strategies/longshot-fade/research/schedule.json"))
fs=[]
for d in sys.argv[1:]:
    f=pd.read_csv(d+"/fills.csv",parse_dates=["time"]); m=pd.read_csv(d+"/markets.csv")[["ticker","result"]]
    fs.append(f.merge(m,on="ticker"))
f=pd.concat(fs)
f["event"]=f.ticker.str.rsplit("-",n=1).str[0]
f=f[f.event.isin(sched)].copy()
f["start"]=f.event.map(lambda e:sched[e]["start"]); f["end"]=f.event.map(lambda e:sched[e]["end"])
t=f.time.dt.as_unit("ns").astype("int64")
frac=(t-f.start)/(f.end-f.start)
f["phase"]=pd.cut(frac,[-9,0,.25,.5,.75,.9,1.0,9],labels=["pre","Q1","Q2","Q3","Q4a","final10%","post"])
y=(f.result=="yes").astype(float); p=f.price/1000
f["gross"]=np.where(f.side=="sell",p-y,y-p)*f.qty
f["net"]=f.gross-np.ceil(np.round(0.0175*f.qty*p*(1-p)*100,6))/100
for k,g in f.groupby("phase",observed=True):
    q=g.qty.sum(); print(f"{str(k):9s} fills {len(g):6d} ctr {q:8.0f} net {100*g.net.sum()/q:6.2f}c games {g.event.nunique()}")
f["ser"]=f.ticker.str.split("-").str[0]
for (s,k),g in f.groupby(["ser","phase"],observed=True):
    q=g.qty.sum(); print(f"  {s} {str(k):9s} ctr {q:8.0f} net {100*g.net.sum()/q:6.2f}c games {g.event.nunique()}")
