import pandas as pd, numpy as np
def fee(p): return 0.07*p*(1-p)
allr=[]
for s in ['KXSOL15M','KXETH15M','KXBTC15M','KXXRP15M','KXDOGE15M']:
    d=pd.read_parquet(f'research/data/{s}.parquet'); o=d[d.h==840].sort_values('close').drop_duplicates('ticker')
    o['open']=o.close-pd.Timedelta(minutes=15); o=o.set_index('open'); 
    grid=pd.date_range(o.index.min(),o.index.max(),freq='15min'); lg=np.log(o.K.reindex(grid)); 
    vol=lg.diff().rolling(288,min_periods=100).std().shift(1)
    o['z1']=((lg-lg.shift(1))/vol).reindex(o.index)
    o['coin']=s; allr.append(o)
o=pd.concat(allr); o['half']=np.where(o.index<'2026-05-01',0,1)
t=1.25
a=o[(o.z1<-t)].dropna(subset=['next_ask']); b=o[(o.z1>t)].dropna(subset=['next_bid'])
x=pd.concat([a.assign(ev=a.y-a.next_ask-fee(a.next_ask)),b.assign(ev=(1-b.y)-(1-b.next_bid)-fee(1-b.next_bid))])
x['hr']=x.index.hour//3*3
print((x.groupby(['hr','half']).ev.agg(['mean','count']).unstack()).round(3))
print((x.groupby(['coin','half']).ev.agg(['mean','count']).unstack()).round(3))
x['side']=np.where(x.z1>0,'afterUP(buyNO)','afterDOWN(buyYES)')
x['mo']=x.index.tz_localize(None).to_period('M')
print(x.groupby(['side','half']).ev.agg(['mean','count']).round(3))
print(x[x.half==1].groupby(['coin','side']).ev.agg(['mean','count']).round(3))
print(x.groupby(['mo','side']).ev.mean().unstack().round(3))
