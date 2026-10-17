import pandas as pd, numpy as np
from sklearn.linear_model import Ridge
def load(s):
    d=pd.read_parquet(f'research/data/{s}.parquet'); o=d[d.h==840].drop_duplicates('ticker')
    return o.set_index('close')
S=load('KXSOL15M'); B=load('KXBTC15M'); E=load('KXETH15M')
cols=['rv_5m','rv_15m','rv_60m','rv_4h']
X=pd.DataFrame(index=S.index)
for c in cols: X['s_'+c]=np.log(S[c]/S.K*100)  # relative
for nm,D in (('b',B),('e',E)):
    for c in cols: X[nm+'_'+c]=np.log((D[c]/D.K*100).reindex(S.index))
y=np.log((S.rv_fut/S.K*100))
X['y']=y; X['iv']=np.log(S.iv/S.K*100); X['mid']=S.mid
X=X.replace([np.inf,-np.inf],np.nan).dropna(subset=[c for c in X if c not in('iv',)])
X['m']=X.index.tz_localize(None).to_period('M')
sc=[c for c in X if c.startswith('s_')]; bc=[c for c in X if c.startswith('b_')]; ec=[c for c in X if c.startswith('e_')]
for name,F in (('own',sc),('own+btc',sc+bc),('own+btc+eth',sc+bc+ec)):
    P=[]
    for m in sorted(X.m.unique())[2:]:
        tr=X[X.m<m]; te=X[X.m==m]
        r=Ridge(1.0).fit(tr[F],tr.y); P.append(pd.Series(r.predict(te[F]),index=te.index))
    p=pd.concat(P); yy=X.y.loc[p.index]
    print(name,len(p),'OOS R2',1-((yy-p)**2).sum()/((yy-yy.mean())**2).sum())
