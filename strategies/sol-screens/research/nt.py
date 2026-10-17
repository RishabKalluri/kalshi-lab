import pandas as pd, numpy as np
from sklearn.linear_model import Ridge
d=pd.read_parquet('research/data/KXSOL15M.parquet')
a=d[d.h==840].drop_duplicates('ticker').set_index('close')
b=d[d.h==60].drop_duplicates('ticker').set_index('close')
X=pd.DataFrame(index=a.index)
for c in ['rv_5m','rv_15m','rv_60m','rv_4h']: X['s_'+c]=np.log(a[c]/a.K*100)
X['nt0']=np.log1p(a.n_trades)
prev=b.n_trades.copy(); prev.index=prev.index+pd.Timedelta(minutes=15)
X['ntprev']=np.log1p(prev.reindex(a.index))
X['ntprev2']=np.log1p(prev.rolling(4,min_periods=1).mean().reindex(a.index))
X['mid_ext']=(a.mid-0.5).abs()
X['y']=np.log(a.rv_fut/a.K*100)
X=X.replace([np.inf,-np.inf],np.nan).dropna()
X['m']=X.index.tz_localize(None).to_period('M')
base=[c for c in X if c.startswith('s_')]
for name,F in (('base',base),('+nt0',base+['nt0']),('+ntprev',base+['ntprev','ntprev2']),('+all',base+['nt0','ntprev','ntprev2'])):
    P=[]
    for m in sorted(X.m.unique())[2:]:
        tr=X[X.m<m]; te=X[X.m==m]
        P.append(pd.Series(Ridge(1.0).fit(tr[F],tr.y).predict(te[F]),index=te.index))
    p=pd.concat(P); yy=X.y.loc[p.index]
    print(name,len(p),1-((yy-p)**2).sum()/((yy-yy.mean())**2).sum())
