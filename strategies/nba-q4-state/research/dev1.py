import pandas as pd, numpy as np, joblib
from sklearn.linear_model import LogisticRegression
exec(open('model1.py').read().split("tr=sn[")[0].split("sn=pd.read_parquet('snaps.parquet')")[1])
m,lr=joblib.load('model1.joblib')
s=pd.read_parquet('snap_quotes.parquet'); s=s[(s.date<'2026-01-01')].dropna(subset=['mid']).copy()
s['p_hgb']=m.predict_proba(feats(s))[:,1]; s['p_lr']=lr.predict_proba(feats(s)[['z','diff','em','pos']])[:,1]
lg=lambda p:np.log(np.clip(p,.01,.99)/(1-np.clip(p,.01,.99)))
def boot(X,y,n=300):
    rng=np.random.default_rng(1); cs=[]
    gid=s.game_id.values; ug=np.unique(gid)
    return None
for T in [None]+sorted(s['T'].unique()):
    d=s if T is None else s[s['T']==T]
    X=np.c_[lg(d.mid),lg(d.p_hgb)]; r=LogisticRegression(C=1e6).fit(X,d.hw)
    r0=LogisticRegression(C=1e6).fit(X[:,:1],d.hw)
    print(T,len(d),'blend',r.coef_.round(2),'mkt-only slope',r0.coef_.round(2),r0.intercept_.round(2))
