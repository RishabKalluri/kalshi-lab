import pandas as pd, numpy as np
rows=[]
for c in ['BTC','ETH','SOL','XRP','DOGE']:
    d=pd.read_parquet(f'research/data/KX{c}15M.parquet'); d['coin']=c; rows.append(d)
d=pd.concat(rows)
d=d[(d.h>=240)&(d.h<=600)&(d.mid>0)]
fav_yes=d.mid>=.5
p=np.where(fav_yes,d.next_ask,1-d.next_bid)
win=np.where(fav_yes,d.y,1-d.y)
d=d.assign(p=p,win=win,fee=0.07*p*(1-p))
d=d[(d.p>0.75)&(d.p<0.97)].copy()
d['net']=d.win-d.p-d.fee
d['mon']=d.close.dt.strftime('%Y-%m')
# one obs per market per h; heat = n_trades rank within coin & h
d['heat']=d.groupby(['coin','h']).n_trades.rank(pct=True)
d['q']=pd.cut(d.heat,[0,.2,.4,.6,.8,1.0])
print(d.groupby('q',observed=True).net.agg(['mean','sem','count']).mul([100,100,1]))
d['half']=np.where(d.mon<'2026-05','A','B')
print(d.groupby(['half','q'],observed=True).net.mean().unstack().mul(100))
print(d.groupby(['coin','q'],observed=True).net.mean().unstack().mul(100))
