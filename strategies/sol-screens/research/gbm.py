import pandas as pd, numpy as np, warnings; warnings.filterwarnings('ignore')
from sklearn.ensemble import HistGradientBoostingClassifier as H
coins=['KXSOL15M','KXETH15M','KXBTC15M','KXXRP15M','KXDOGE15M']
fr=[]
for ci,s in enumerate(coins):
    d=pd.read_parquet(f'research/data/{s}.parquet')
    base=d[d.h==840].drop_duplicates('ticker').copy(); base['open']=base.close-pd.Timedelta(minutes=15)
    K=base.set_index('open').K; K=K[~K.index.duplicated()]
    grid=pd.date_range(K.index.min(),K.index.max(),freq='15min'); lg=np.log(K.reindex(grid))
    vol=lg.diff().rolling(288,min_periods=100).std().shift(1)
    z=pd.DataFrame({f'z{n}':(lg-lg.shift(n))/(vol*np.sqrt(n)) for n in (1,2,4,8)})
    d['open']=d.close-pd.Timedelta(minutes=15)
    d=d.join(z,on='open'); d['coin']=ci
    fr.append(d)
d=pd.concat(fr,ignore_index=True)
d['sig']=d.rv_60m*np.sqrt(d.h)
d['Dn']=d.D/d.sig; d['Dn15']=d.D/(d.rv_15m*np.sqrt(d.h)); d['Dn5']=d.D/(d.rv_5m*np.sqrt(d.h))
d['r5']=np.log(d.rv_5m/d.rv_60m); d['r15']=np.log(d.rv_15m/d.rv_60m); d['r4h']=np.log(d.rv_4h/d.rv_60m)
d['ivr']=np.log(d.iv/d.rv_60m)
d['spr']=d.ask-d.bid; d['lna']=np.log1p(d.age_ask); d['lnb']=np.log1p(d.age_bid); d['nt']=np.log1p(d.n_trades)
et=d.close.dt.tz_convert('America/New_York'); d['hs']=np.sin(2*np.pi*(et.dt.hour+et.dt.minute/60)/24); d['hc']=np.cos(2*np.pi*(et.dt.hour+et.dt.minute/60)/24)
d['dow']=et.dt.dayofweek
d['mo']=d.close.dt.tz_localize(None).dt.to_period('M')
F=['h','mid','spr','Dn','Dn15','Dn5','r5','r15','r4h','ivr','lna','lnb','nt','hs','hc','dow','coin','z1','z2','z4','z8']
d=d.dropna(subset=['mid','Dn','y'])
def fee(p): return 0.07*p*(1-p)
months=sorted(d.mo.unique()); out=[]
for m in months[4:]:
    tr=d[d.mo<m]; te=d[d.mo==m]
    mdl=H(max_iter=150,learning_rate=0.05,max_leaf_nodes=15,min_samples_leaf=300,l2_regularization=5).fit(tr[F],tr.y)
    out.append(te.assign(p=mdl.predict_proba(te[F])[:,1]))
r=pd.concat(out); r.to_pickle('/tmp/gbm_oos.pkl')
print(len(r),'brier model',((r.p-r.y)**2).mean(),'mid',((r.mid-r.y)**2).mean())
for thr in (0.03,0.05,0.08,0.12):
    a=r[(r.p-r.next_ask>thr)].dropna(subset=['next_ask']); b=r[(r.next_bid-r.p>thr)].dropna(subset=['next_bid'])
    ev=pd.concat([a.y-a.next_ask-fee(a.next_ask),(1-b.y)-(1-b.next_bid)-fee(1-b.next_bid)]); mo=pd.concat([a.mo,b.mo]).values
    mm=ev.groupby(mo).mean()
    print(thr,len(ev),round(ev.mean()*100,2),'se',round(ev.std()/np.sqrt(len(ev))*100,2),'months+',(mm>0).sum(),'/',len(mm))
