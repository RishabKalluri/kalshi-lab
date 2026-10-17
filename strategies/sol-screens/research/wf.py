import pandas as pd, numpy as np
from sklearn.linear_model import LogisticRegression
o=pd.read_pickle('/tmp/sol_trend.pkl')
d=pd.read_parquet('research/data/KXSOL15M.parquet')
# z1: last window
K=o.K; 
o['lr1']=np.log(o.K/o.K.shift(1,freq='15min').reindex(o.index).values) if False else np.nan
grid=pd.date_range(o.index.min(),o.index.max(),freq='15min')
lg=np.log(o.K.reindex(grid)); vol=lg.diff().rolling(288,min_periods=100).std().shift(1)
o['z1']=((lg-lg.shift(1))/vol).reindex(o.index)
o['Dn']=o.D/(o.rv_60m*np.sqrt(840)) 
o['rr']=np.log(o.rv_5m/o.rv_60m)
et=o.index.tz_convert('America/New_York')
o['hs']=np.sin(2*np.pi*et.hour/24);o['hc']=np.cos(2*np.pi*et.hour/24);o['wk']=(et.dayofweek>=5).astype(float)
F=['z1','z2','z4','z8','z16','Dn','rr','hs','hc','wk','mid']
o=o.dropna(subset=F+['y'])
o['m']=o.index.to_period('M')
def fee(p): return 0.07*p*(1-p)
out=[]
for m in sorted(o.m.unique())[3:]:
    tr=o[o.m<m]; te=o[o.m==m]
    lr=LogisticRegression(C=0.3,max_iter=500).fit(tr[F].clip(-4,4),tr.y)
    te=te.assign(p=lr.predict_proba(te[F].clip(-4,4))[:,1])
    out.append(te)
r=pd.concat(out)
print(len(r), 'brier model',((r.p-r.y)**2).mean(),'mkt',((r.mid-r.y)**2).mean())
for thr in (0.02,0.04,0.06,0.08):
    a=r[(r.p-r.next_ask-0.0>thr)].dropna(subset=['next_ask']); b=r[(r.next_bid-r.p>thr)].dropna(subset=['next_bid'])
    py=a.y-a.next_ask-fee(a.next_ask); pn=(1-b.y)-(1-b.next_bid)-fee(1-b.next_bid)
    x=pd.concat([py,pn]); mo=pd.concat([a.m,b.m])
    mm=x.groupby(mo.values).mean()
    print(thr,len(x),round(x.mean()*100,2),'se',round(x.std()/np.sqrt(len(x))*100,2),'months+',(mm>0).sum(),'/',len(mm))
