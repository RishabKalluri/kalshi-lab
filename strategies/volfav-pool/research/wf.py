import pandas as pd, numpy as np, sys
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
d = pd.read_parquet('/srv/kalshi/strategies/volfav-pool/research/trades2.parquet')
d['zm']=np.abs(norm.ppf(d.mid)); d['zf']=np.abs(d.D)/(d.fc*np.sqrt(d.h-40)); d['gap']=d.zf-d.zm
d['lr']=np.log(d.ratio)
d['we']=(d.dow>=5).astype(float)
d['month']=d.close.dt.strftime('%Y-%m')
d['lh']=np.log(d.h)
d['zpx']=np.abs(norm.ppf(d.px))
FEATS=sys.argv[1].split(',') if len(sys.argv)>1 else ['zm','zf']
months=sorted(d.month.unique())
res=[]
for m in months[3:]:
    tr=d[d.month<m]; te=d[d.month==m].copy()
    clf=LogisticRegression(C=1.0,max_iter=500).fit(tr[FEATS],tr.win)
    te['p']=clf.predict_proba(te[FEATS])[:,1]
    res.append(te)
r=pd.concat(res); r['pe']=(r.p-r.px-r.fee)*100
print('coef last', dict(zip(FEATS,clf.coef_[0].round(3))))
r['eb']=pd.cut(r.pe,[-100,-3,-1,0,0.5,1,1.5,2,3,5,100])
print(r.groupby('eb',observed=True).agg(n=('pc','size'),pred=('pe','mean'),real=('pc','mean'),mk=('ticker','nunique')).round(2))
for t in [0.5,1,1.5,2,3]:
    s=r[r.pe>t]; mk=s.groupby('ticker').pc.agg(['sum','size'])
    se=np.sqrt(((mk['sum']-mk['size']*s.pc.mean())**2).sum())/mk['size'].sum()
    print(f'thr>{t}: rows {len(s)} markets {s.ticker.nunique()} mean {s.pc.mean():.2f}c se~{se:.2f}  by month', s.groupby('month').pc.mean().round(1).to_dict())
    print('   by coin', s.groupby('coin').pc.agg(['mean','size']).round(2).T.to_dict())
r.to_parquet('/srv/kalshi/strategies/volfav-pool/research/wf_out.parquet')
