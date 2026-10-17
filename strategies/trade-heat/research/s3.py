import pandas as pd, numpy as np
rows=[]
for c in ['BTC','ETH','SOL','XRP','DOGE']:
    d=pd.read_parquet(f'research/data/KX{c}15M.parquet'); d['coin']=c; rows.append(d)
D=pd.concat(rows); D=D[D.mid>0]
D['mon']=D.close.dt.strftime('%Y-%m'); D['half']=np.where(D.mon<'2026-05','A','B')
w=D[D.h==600][['coin','close','K','rv_60m','mid','y','next_ask','next_bid','half']].copy()
w=w.reset_index(drop=True)
w['min']=w.close.dt.minute
# hour start strike = K of the window closing at :15 minus 15 min -> K of window with close hh:15 is the hour open strike
base=w[w['min']==15][['coin','close','K']].copy(); base['hour']=(base.close-pd.Timedelta(seconds=1)).dt.floor('h'); base=base.rename(columns={'K':'K0'})[['coin','hour','K0']]
w['hour']=(w.close-pd.Timedelta(seconds=1)).dt.floor('h')
w=w.merge(base,on=['coin','hour'],how='left')
w['z']=(w.K-w.K0)/(w.K0*w.rv_60m.clip(lower=1e-9)/ (w.S if 'S' in w else 1)) if False else (w.K-w.K0)/w.K0
w['sig']=w.rv_60m*np.sqrt(900)/ (w.K)   # rv in $/sqrt(s) -> relative per 15min
for m,name in [(45,':45 window'),(30,':30 window')]:
    s=w[w['min']==m].copy()
    nwin={45:3,30:2}[m]
    s['zz']=s.z/(s.sig*np.sqrt(nwin)*1.0)
    s['zq']=pd.qcut(s.zz,5,labels=False)
    s['res']=s.y-s.mid
    print(name); print(s.groupby(['half','zq']).res.agg(['mean','sem','count']).mul([100,100,1]).round(2).unstack(0))
