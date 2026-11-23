import pandas as pd, numpy as np, joblib
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.linear_model import LogisticRegression
sn=pd.read_parquet('nhl_snaps.parquet')
def feats(d):
    lg=np.log(d.pm/(1-d.pm))
    return pd.DataFrame({'diff':d['diff'],'sec':d.sec,'lgpm':lg,'ou':d.ou.fillna(6),'tot':d.tot,'z':(d['diff']+0.5*(d.pm-.5)*d.sec/1200*4)/np.sqrt(np.maximum(d.sec,30)/3600*6)})
def LL(y,p): p=np.clip(p,1e-3,1-1e-3); return -(y*np.log(p)+(1-y)*np.log(1-p)).mean()
tr=sn[sn.date<'2025-09-25']; print('train games',tr.game_id.nunique())
m=HGB(max_iter=200,learning_rate=0.05,max_leaf_nodes=8,min_samples_leaf=150,l2_regularization=10,random_state=0).fit(feats(tr),tr.hw)
lr=LogisticRegression(C=10,max_iter=3000).fit(feats(tr)[['z','diff','lgpm']],tr.hw)
joblib.dump((m,lr),'nhl_model.joblib')
S=pd.read_parquet('nhl_snap_quotes.parquet').dropna(subset=['mid']).copy()
S['p_hgb']=m.predict_proba(feats(S))[:,1]; S['p_lr']=lr.predict_proba(feats(S)[['z','diff','lgpm']])[:,1]
dev=S[S.date<'2026-01-01']; print('dev games',dev.game_id.nunique())
for T in sorted(S['T'].unique()):
    d=dev[dev['T']==T]; print(T,len(d),'kalshi',round(LL(d.hw,d.mid),4),'hgb',round(LL(d.hw,d.p_hgb),4),'lr',round(LL(d.hw,d.p_lr),4),'pregame ml',round(LL(d.hw,d.pm),4))
fee=lambda p:0.07*p*(1-p)
def rep(d,p,thr=.02,lab=''):
    d=d.copy(); ey=p-d.ask-fee(d.ask); en=(1-p)-(1-d.bid)-fee(1-d.bid)
    ty=(ey>=thr)&d.ask.notna(); tn=(en>=thr)&d.bid.notna()&~ty
    pnl=np.r_[(d.hw-d.ask-fee(d.ask))[ty].values,((1-d.hw)-(1-d.bid)-fee(1-d.bid))[tn].values]
    g=np.r_[d.game_id[ty].values,d.game_id[tn].values]
    if len(pnl)==0: print(lab,'none'); return
    df=pd.DataFrame({'g':g,'p':pnl}).groupby('g').p.agg(['sum','count']); rng=np.random.default_rng(0)
    bs=[df['sum'].values[i].sum()/df['count'].values[i].sum() for i in (rng.integers(0,len(df),len(df)) for _ in range(1500))]
    print(f'{lab}: n {len(pnl)} games {len(df)} realized {pnl.mean()*100:.2f}c CI [{np.percentile(bs,2.5)*100:.2f},{np.percentile(bs,97.5)*100:.2f}]')
for T in [None,300,180,120,600,1200]:
    d=dev if T is None else dev[dev['T']==T]
    rep(d,d.p_hgb,.02,f'DEV hgb T={T}')
