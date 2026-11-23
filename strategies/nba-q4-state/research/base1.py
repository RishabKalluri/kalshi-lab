import pandas as pd, numpy as np
from sklearn.linear_model import LogisticRegression
from scipy.stats import norm
st=pd.read_parquet('states.parquet'); q=pd.read_parquet('quotes.parquet')
st['diff3']=st.h3-st.a3; st['homewin']=(st.hf>st.af).astype(int)
st['fm']=st.hf-st.af
print('corr exp_margin vs final margin',st[['exp_margin','fm']].corr().iloc[0,1])
print(st.groupby('season').apply(lambda x: pd.Series(dict(n=len(x),sd_resid=(x.fm-x.exp_margin).std(), home_pct=x.homewin.mean()))))
st=st.dropna(subset=['exp_margin'])
def LL(y,p): p=np.clip(p,1e-4,1-1e-4); return -(y*np.log(p)+(1-y)*np.log(1-p)).mean()
tr=st[st.season<=2025]; te=st[st.season==2026]
X=lambda d:np.c_[d.diff3,d.exp_margin]
lr=LogisticRegression(C=100).fit(X(tr[tr.season<=2024]),tr[tr.season<=2024].homewin)
print('coefs',lr.coef_,lr.intercept_)
for s in [2023,2024,2025,2026]:
    d=st[st.season==s]; print(s,'LL logit',LL(d.homewin,lr.predict_proba(X(d))[:,1]), 'LL spread only')
# gaussian
t=tr[tr.season<=2024]; 
res=(t.fm-t.diff3-0.25*t.exp_margin); print('remaining resid sd',res.std(), 'mean',res.mean())
# join kalshi
h=q.merge(st[['game_id','h','a']] if False else st[['game_id','home','away','diff3','exp_margin','homewin','date']],on='game_id')
hm=h[h.h==h.home.map({'NO':'NOP'}).fillna(h.home)] if False else h
KM={'BKN':'BKN','NOP':'NO','GSW':'GS','SAS':'SA','NYK':'NY','WAS':'WSH','UTA':'UTAH'}
h=h[(h.team==h.h)].drop_duplicates('game_id')
h['ph']=lr.predict_proba(X(h))[:,1]
print(len(h), h.date.min(), h.date.max())
for nm,d in [('all',h),('Oct-Dec',h[h.date<'2026-01-01']),('Jan+',h[h.date>='2026-01-01'])]:
    d=d.dropna(subset=['p_break'])
    print(nm,len(d),'LL kalshi',LL(d.homewin,d.p_break),'LL model',LL(d.homewin,d.ph),'LL kalshi@endq3',LL(d.homewin,d.p_endq3.fillna(d.p_break)))
h[['game_id','ph']].to_parquet('tmp_ph.parquet')
