import pandas as pd, numpy as np
from sklearn.ensemble import HistGradientBoostingClassifier as HGB
from sklearn.linear_model import LogisticRegression
sn=pd.read_parquet('snaps.parquet')
def feats(d):
    x=pd.DataFrame({'diff':d['diff'],'sec':d.sec,'em':d.em,'tot':d.tot,'pos':d.pos})
    x['z']=(d['diff']+d.em*d.sec/2880*0.9)/np.sqrt(d.sec/2880*100+25)   # gaussian-ish scaled lead
    x['pace']=d.tot/(2880-d.sec+1)*48
    x['posdiff']=d.pos*(d.sec<300)
    return x
def LL(y,p): p=np.clip(p,1e-4,1-1e-4); return -(y*np.log(p)+(1-y)*np.log(1-p)).mean()
tr=sn[sn.season<=2024]; dv=sn[sn.season==2025]
m=HGB(max_iter=300,learning_rate=0.05,max_leaf_nodes=15,min_samples_leaf=200,l2_regularization=5,random_state=0).fit(feats(tr),tr.hw)
lr=LogisticRegression(C=10,max_iter=2000).fit(feats(tr)[['z','diff','em','pos']],tr.hw)
for T in sorted(sn['T'].unique()):
    d=dv[dv['T']==T]
    print(T,len(d),'HGB',round(LL(d.hw,m.predict_proba(feats(d))[:,1]),4),'LR',round(LL(d.hw,lr.predict_proba(feats(d)[['z','diff','em','pos']])[:,1]),4))
import joblib; joblib.dump((m,lr),'model1.joblib')
# Kalshi dev comparison (Oct-Dec 2025 only)
s=pd.read_parquet('snap_quotes.parquet'); s=s[(s.date<'2026-01-01')].dropna(subset=['mid'])
s['p_hgb']=m.predict_proba(feats(s))[:,1]; s['p_lr']=lr.predict_proba(feats(s)[['z','diff','em','pos']])[:,1]
print('Oct-Dec dev vs Kalshi mid')
for T in sorted(sn['T'].unique()):
    d=s[s['T']==T]; print(T,len(d),'kalshi',round(LL(d.hw,d.mid),4),'HGB',round(LL(d.hw,d.p_hgb),4),'LR',round(LL(d.hw,d.p_lr),4))
