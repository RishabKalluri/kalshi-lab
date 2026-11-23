import pandas as pd, numpy as np, joblib, sys
exec(open('model1.py').read().split("tr=sn[")[0].split("sn=pd.read_parquet('snaps.parquet')")[1])
from sklearn.linear_model import LogisticRegression
m,lr=joblib.load('model1.joblib')
lg=lambda p:np.log(np.clip(p,.01,.99)/(1-np.clip(p,.01,.99))); sg=lambda z:1/(1+np.exp(-z))
S=pd.read_parquet('snap_quotes.parquet').dropna(subset=['mid']).copy()
S['p_hgb']=m.predict_proba(feats(S))[:,1]
dev=S[S.date<'2026-01-01']; tst=S[S.date>='2026-01-01']
fee=lambda p:0.07*p*(1-p)
def replay(d,pstar,thr=0.02,label=''):
    d=d.copy(); d['ps']=pstar
    # buy YES at ask (next yes-taker print), buy NO at 1-bid
    ey=d.ps-d.ask-fee(d.ask); en=(1-d.ps)-(1-d.bid)-fee(1-d.bid)
    ty=(ey>=thr)&d.ask.notna(); tn=(en>=thr)&d.bid.notna()&~ty
    pnl=np.r_[ (d.hw-d.ask-fee(d.ask))[ty].values, ((1-d.hw)-(1-d.bid)-fee(1-d.bid))[tn].values ]
    gid=np.r_[d.game_id[ty].values,d.game_id[tn].values]; ex=np.r_[ey[ty].values,en[tn].values]
    n=len(pnl)
    if n==0: print(label,'no trades'); return
    # game-clustered bootstrap
    df=pd.DataFrame({'g':gid,'p':pnl}); gs=df.groupby('g').p.agg(['sum','count']); rng=np.random.default_rng(0)
    bs=[]; 
    for _ in range(2000):
        i=rng.integers(0,len(gs),len(gs)); bs.append(gs['sum'].values[i].sum()/gs['count'].values[i].sum())
    print(f'{label}: trades {n} games {gs.shape[0]} realized {pnl.mean()*100:.2f}c CI [{np.percentile(bs,2.5)*100:.2f},{np.percentile(bs,97.5)*100:.2f}] expected {ex.mean()*100:.2f}c  vol60 median {d.vol60.median():.0f}')
    return pnl
if __name__=='__main__':
    X=np.c_[lg(dev.mid),lg(dev.p_hgb)]; r=LogisticRegression(C=1e6).fit(X,dev.hw); print('blend fit',r.coef_,r.intercept_)
    joblib.dump(r,'blend.joblib')
    for thr in [0.0,0.02,0.04]:
        replay(dev,sg(r.decision_function(X)),thr,f'DEV blend thr{thr}')
        replay(dev,dev.p_hgb,thr,f'DEV hgb-only thr{thr}')
