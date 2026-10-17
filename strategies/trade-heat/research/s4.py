import pandas as pd, numpy as np
rows=[]
for c in ['BTC','ETH','SOL','XRP','DOGE']:
    d=pd.read_parquet(f'research/data/KX{c}15M.parquet'); d['coin']=c; rows.append(d)
D=pd.concat(rows); D=D[D.mid>0].copy()
D['mon']=D.close.dt.strftime('%Y-%m'); D['wk']=D.close.dt.dayofweek>=5
fy=D.mid>=.5
p=np.where(fy,D.next_ask,1-D.next_bid); win=np.where(fy,D.y,1-D.y)
D['p']=p; D['net']=win-p-0.07*p*(1-p)
X=D[(D.h>=240)&(D.h<=720)&D.p.notna()]
for lo,hi in [(.75,.9),(.9,.95),(.95,.99)]:
    Y=X[(X.p>lo)&(X.p<=hi)]
    # one obs per market: first h
    Y=Y.sort_values('h',ascending=False).groupby(['coin','ticker']).head(1)
    print(lo,hi); print(Y.groupby(['wk']).net.agg(['mean','sem','count']).mul([100,100,1]).round(2))
    print(Y[Y.wk].groupby('mon').net.mean().mul(100).round(2).to_dict())
    print(Y[Y.wk].groupby('coin').net.agg(['mean','count']).round(4).T)
