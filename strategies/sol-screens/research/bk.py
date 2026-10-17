import pandas as pd, numpy as np
def zs(s):
    d=pd.read_parquet(f'research/data/{s}.parquet'); o=d[d.h==840].sort_values('close')
    o['open']=o.close-pd.Timedelta(minutes=15); K=o.set_index('open').K; K=K[~K.index.duplicated()]
    grid=pd.date_range(K.index.min(),K.index.max(),freq='15min'); lg=np.log(K.reindex(grid))
    vol=lg.diff().rolling(288,min_periods=100).std().shift(1)
    return ((lg-lg.shift(1))/vol)
z=pd.DataFrame({c:zs(f'KXC{c}15M'.replace('KXC','KX')) for c in ['SOL','BTC','ETH']})
o=pd.read_pickle('/tmp/sol_trend.pkl').join(z.add_prefix('z1_'))
def fee(p): return 0.07*p*(1-p)
def rep(name,s):
    out=[]
    for hf in (0,1):
        t=s[s.half==hf]; a=t.dropna(subset=['next_ask']); b=t.dropna(subset=['next_bid'])
        out.append((len(t), round((a.y-a.next_ask-fee(a.next_ask)).mean()*100,2), round(((1-b.y)-(1-b.next_bid)-fee(1-b.next_bid)).mean()*100,2)))
    print(name,out)
zs_=o.z1_SOL; ob=(o.z1_BTC+o.z1_ETH)/2
for thr in (1.5,1.0):
  dn=o[zs_<-thr]; up=o[zs_>thr]
  rep(f'SOL down>{thr}, btc/eth also down<-0.75 (buyYES; col3 irrelevant)',dn[ob[dn.index]<-0.75])
  rep(f'SOL down>{thr}, btc/eth not down',dn[ob[dn.index]>=-0.75])
  rep(f'SOL up>{thr}, btc/eth also up (buyNO = col3)',up[ob[up.index]>0.75])
  rep(f'SOL up>{thr}, btc/eth not up',up[ob[up.index]<=0.75])
