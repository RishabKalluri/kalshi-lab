import numpy as np, pandas as pd, sys
from sklearn.ensemble import HistGradientBoostingClassifier as H
d=pd.read_parquet('research/data/KXSOL15M.parquet')
d=d[d.mid.notna()].copy()
sq=np.sqrt(d.h.clip(lower=1))
d['z']=d.D/(d.rv_15m*sq+1e-9); d['zm']=d.D/(d.rv_60m*sq+1e-9)
d['miss']=d.mid.clip(0.01,0.99); d['lg']=np.log(d.miss/(1-d.miss))
d['spr']=d.ask-d.bid; d['r5']=d.rv_5m/d.rv_60m; d['r4']=d.rv_60m/d.rv_4h
d['ivr']=d.iv/d.rv_60m
t=d.close
d['hr']=t.dt.hour+t.dt.minute/60; d['dow']=t.dt.dayofweek
d['moveD']=d.D/d.S*1e4
F=['h','z','zm','lg','spr','r5','r4','ivr','hr','dow','moveD','age_ask','age_bid','n_trades','rv_60m']
d['month']=t.dt.strftime('%Y-%m')
months=sorted(d.month.unique())
def fee(p): return 0.07*p*(1-p)
out=[]
for i,m in enumerate(months):
    if i<3: continue
    tr=d[d.month.isin(months[:i])]; te=d[d.month==m]
    clf=H(max_iter=150,learning_rate=0.05,max_depth=4,min_samples_leaf=200,l2_regularization=1.0)
    clf.fit(tr[F],tr.y); te=te.assign(p=clf.predict_proba(te[F])[:,1])
    out.append(te)
o=pd.concat(out)
print('brier model',((o.p-o.y)**2).mean(),'mkt',((o.mid-o.y)**2).mean())
rows=[]
for side in ['buy','sell']:
    if side=='buy':
        px=o.next_ask; e=o.p-px; pnl=o.y-px-fee(px)
    else:
        px=o.next_bid; e=px-o.p; pnl=px-o.y-fee(px)
    for thr in [0.02,0.04,0.06,0.08,0.10]:
        s=(e>thr)&px.notna()
        x=o[s].assign(pnl=pnl[s])
        mk=x.groupby('ticker').pnl.first()  # first signal per market (h descending order?) 
        print(side,thr,'rows',s.sum(),'mkts',len(mk),'mean c %.2f'%(100*mk.mean()),'se %.2f'%(100*mk.std()/max(len(mk),1)**.5))
