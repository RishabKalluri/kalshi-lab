import pandas as pd, numpy as np
fee=lambda p:0.07*p*(1-p)
for coin in ['KXXRP15M','KXDOGE15M','KXETH15M','KXBTC15M','KXSOL15M']:
    d=pd.read_parquet(f'research/data/{coin}.parquet'); d=d[(d.close<'2026-09-01')&d.h.between(60,600)].copy()
    d['slot']=(d.close.dt.minute//15); d['half']=np.where(d.close<'2026-06-01','A','B')
    up=d.mid>=0.5
    # dog: if mid>=.5 dog is NO at 1-next_bid ; else dog is YES at next_ask
    pxd=np.where(up,1-d.next_bid,d.next_ask); won=np.where(up,1-d.y,d.y)
    d['e_dog']=won-pxd-fee(pxd)
    d['gap']=np.abs(d.next_ask-d.next_bid)
    # restrict to underdog priced 10-45c
    x=d[(pxd>=0.10)&(pxd<=0.45)].dropna(subset=['e_dog'])
    t=x.groupby(['slot','half']).e_dog.agg(['mean','count']).unstack()
    print(coin,'underdog 10-45c buy at next fill'); print((t['mean']*100).round(2).assign(nA=t['count']['A'],nB=t['count']['B']).to_string())
