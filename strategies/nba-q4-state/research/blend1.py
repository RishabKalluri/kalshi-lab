import pandas as pd, numpy as np
from sklearn.linear_model import LogisticRegression
q=pd.read_parquet('quotes.parquet'); ph=pd.read_parquet('tmp_ph.parquet')
st=pd.read_parquet('states.parquet')[['game_id','home','date','h3','a3','exp_margin']]
d=q.merge(ph,on='game_id').merge(st,on='game_id')
d=d[(d.team==d.h)].drop_duplicates('game_id')
d=d.dropna(subset=['p_break']); d['y']=d.sv
lg=lambda p:np.log(np.clip(p,.01,.99)/(1-np.clip(p,.01,.99)))
for nm,s in [('Oct-Dec',d[d.date<'2026-01-01']),('Jan+',d[d.date>='2026-01-01'])]:
    X=np.c_[lg(s.p_break),lg(s.ph)]; r=LogisticRegression(C=1e6).fit(X,s.y.astype(int)); print(nm,len(s),r.coef_,r.intercept_)
    # bootstrap se of coefs
    rng=np.random.default_rng(0); cs=[]
    for _ in range(200):
        i=rng.integers(0,len(s),len(s)); cs.append(LogisticRegression(C=1e6).fit(X[i],s.y.values[i].astype(int)).coef_[0])
    print(' se',np.std(cs,0))
# calibration of kalshi mid: both sides
a=q.dropna(subset=['p_break']).copy(); a['bin']=pd.cut(a.p_break,[0,.05,.1,.2,.3,.4,.5,.6,.7,.8,.9,.95,1])
print(a.groupby('bin').agg(n=('sv','size'),p=('p_break','mean'),win=('sv','mean')).round(3))
# spread proxy
b=q.dropna(subset=['last_ask','last_bid']); print('ask-bid median',(b.last_ask-b.last_bid).median(), (b.last_ask-b.last_bid).mean())
