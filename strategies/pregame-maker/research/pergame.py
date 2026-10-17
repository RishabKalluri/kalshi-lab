import sys, numpy as np, pandas as pd
fs=[]
for d in sys.argv[1:]:
    f=pd.read_csv(d+"/fills.csv"); m=pd.read_csv(d+"/markets.csv")[["ticker","result"]]; fs.append(f.merge(m,on="ticker"))
f=pd.concat(fs); y=(f.result=="yes").astype(float); p=f.price/1000
f["net"]=np.where(f.side=="sell",p-y,y-p)*f.qty-np.ceil(np.round(0.0175*f.qty*p*(1-p)*100,6))/100
f["event"]=f.ticker.str.rsplit("-",n=1).str[0]
g=f.groupby("event").agg(net=("net","sum"),q=("qty","sum"))
print("games",len(g),"total $",round(g.net.sum(),1),"mean $/game",round(g.net.mean(),2),"win share",round((g.net>0).mean(),3))
print("worst 10 games $:",g.net.nsmallest(10).round(1).tolist()); print("best 10:",g.net.nlargest(10).round(1).tolist())
s=g.net.sort_values(); k=int(len(s)*0.01)
print("total excluding worst 1% games $",round(s.iloc[k:].sum(),1),"; excluding best 1% $",round(s.iloc[:-k].sum(),1))
print("per-game net ¢/ctr quantiles",(100*g.net/g.q).quantile([.05,.25,.5,.75,.95]).round(1).tolist())
