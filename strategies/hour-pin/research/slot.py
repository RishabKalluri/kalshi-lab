import pandas as pd, numpy as np, sys
fee=lambda p:0.07*p*(1-p)
for coin in ['KXXRP15M','KXDOGE15M','KXETH15M','KXBTC15M','KXSOL15M']:
    d=pd.read_parquet(f'research/data/{coin}.parquet'); d=d[(d.close<'2026-09-01')&d.h.between(60,600)].copy()
    d['slot']=(d.close.dt.minute//15)  # close slot: 0 => closes on the hour
    d['half']=np.where(d.close<'2026-06-01','A','B')
    for lab,m in (('fav',d.mid>=0.5),('dog',d.mid<0.5)):
        x=d[m]
        # buy side of mid>=.5 -> YES at next_ask; mid<.5 -> NO at 1-next_bid  (underdog = NO side when mid>=.5); define by side bought
    # favourite buy
    fv=d[d.mid>=0.5].copy(); fv['px']=fv.next_ask; fv['e']=fv.y-fv.px-fee(fv.px)
    fl=d[d.mid<0.5].copy(); fl['px']=1-fl.next_bid; fl['e']=(1-fl.y)-fl.px-fee(fl.px)
    f=pd.concat([fv.assign(side='fav'),fl.assign(side='fav')]) # favourite for mid<.5 is NO
    f['e']=np.where(f.mid>=.5, f.y-f.next_ask-fee(f.next_ask), (1-f.y)-(1-f.next_bid)-fee(1-f.next_bid))
    f=f.dropna(subset=['e'])
    t=f.groupby(['slot','half']).e.agg(['mean','count']).unstack()
    print(coin); print((t['mean']*100).round(2).assign(nA=t['count']['A'],nB=t['count']['B']).to_string())
