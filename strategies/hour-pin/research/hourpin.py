import pandas as pd, numpy as np
fee=lambda p:0.07*p*(1-p)
fr=[]
for coin in ['KXBTC15M','KXETH15M','KXXRP15M','KXSOL15M','KXDOGE15M']:
    d=pd.read_parquet(f'research/data/{coin}.parquet'); d=d[(d.close<'2026-09-01')&d.h.isin([240,180,120,60])].copy()
    d['coin']=coin[2:-3]; fr.append(d)
d=pd.concat(fr)
d['slot']=d.close.dt.minute//15; d['mon']=d.close.dt.strftime('%m'); d['hr']=d.close.dt.hour; d['dow']=d.close.dt.dayofweek
up=d.mid>=0.5
d['px']=np.where(up,d.next_ask,1-d.next_bid); d['won']=np.where(up,d.y,1-d.y)
d['e']=d.won-d.px-fee(d.px)
# dog
d['pxd']=np.where(up,1-d.next_bid,d.next_ask); d['wond']=np.where(up,1-d.y,d.y); d['ed']=d.wond-d.pxd-fee(d.pxd)
f=d[(d.px>=0.85)&(d.px<=0.98)].dropna(subset=['e'])
# one entry per market: first checkpoint (largest h) meeting the filter
f=f.sort_values(['ticker','h'],ascending=[True,False]).groupby('ticker').head(1)
print('markets',len(f))
for s in (0,1,2,3):
    x=f[f.slot==s]; mt=x.groupby('mon').e.mean()
    print('slot',s,'n',len(x),'edge %.2f'%(x.e.mean()*100),'se %.2f'%(x.e.std()/np.sqrt(len(x))*100),'months+',(mt>0).sum(),'/',len(mt))
x=f[f.slot==0]
print('slot0 by coin',(x.groupby('coin').e.mean()*100).round(2).to_dict(), x.groupby('coin').size().to_dict())
print('slot0 by month',(x.groupby('mon').e.mean()*100).round(2).to_dict())
print('slot0 by close hour UTC',(x.groupby('hr').e.mean()*100).round(1).to_dict())
print('slot0 by weekend',(x.groupby(x.dow>=5).e.mean()*100).round(2).to_dict())
# slot0 by day clustered se
dm=x.groupby(x.close.dt.date).e.mean(); print('day-clustered mean %.2f se %.2f days %d'%(dm.mean()*100,dm.std()/np.sqrt(len(dm))*100,len(dm)))
# slot1 dog
g=d[(d.px>=0.85)&(d.px<=0.98)].dropna(subset=['ed']); g=g.sort_values(['ticker','h'],ascending=[True,False]).groupby('ticker').head(1)
for s in (0,1,2,3):
    y=g[g.slot==s]; print('dog slot',s,len(y),'edge %.2f'%(y.ed.mean()*100))
