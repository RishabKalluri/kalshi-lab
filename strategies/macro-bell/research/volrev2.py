import pandas as pd, numpy as np
def fee(p): return 0.07*p*(1-p)
v=pd.read_parquet('/tmp/solvol15.parquet').vol
rel=v/ v.groupby(v.index.time).transform(lambda s: s.rolling(14,min_periods=7).median().shift(1))
d=pd.read_parquet('research/data/KXSOL15M.parquet'); d=d[(d.close<'2026-09-01')&(d.h.isin([840,780,720]))].copy()
d['open']=(d.close-pd.Timedelta(minutes=15)).astype('datetime64[ns, UTC]')
d['close']=d.close.astype('datetime64[ns, UTC]')
k=d[d.h==840][['open','K','rv_15m']].drop_duplicates('open').set_index('open')
d['Kprev']=d.open.map(k.K.rename(index=lambda x:x+pd.Timedelta(minutes=15)))
d['relv']=(d.open-pd.Timedelta(minutes=15)).map(rel)
d['z1']=np.log(d.K/d.Kprev)/ (d.rv_15m)
print(d.Kprev.notna().sum(), d.relv.notna().sum(), len(d))
d=d.dropna(subset=["z1","relv"]); d['half']=np.where(d.close<'2026-05-01',0,1)
d=d[d.z1.abs()<d.z1.abs().quantile(.999)]
d['z1']=d.z1/(1.4826*d.z1.abs().median())
d=d[d.z1.abs()>1.25]
def ev(x):
    up=x.z1>0
    # fade: after up move buy NO (sell YES at next_bid); after down buy YES at next_ask
    n=x[up].dropna(subset=['next_bid']); y=x[~up].dropna(subset=['next_ask'])
    e=np.r_[(1-n.y)-(1-n.next_bid)-fee(1-n.next_bid), y.y-y.next_ask-fee(y.next_ask)]
    return e
d['rb']=pd.qcut(d.relv,3,labels=['low','mid','high'])
for (h,rb),x in d.groupby(['half','rb'],observed=True):
    e=ev(x); print('half',h,rb,len(e),round(e.mean()*100,2),'se',round(e.std()/len(e)**.5*100,2))
print('--- h=840 only, by month, relv top tercile vs rest')
d1=d[d.h==840].copy(); d1['m']=d1.close.dt.strftime('%m'); d1['hi']=d1.relv>d1.relv.quantile(2/3)
for (m,hi),x in d1.groupby(['m','hi']):
    e=ev(x); print(m,hi,len(e),round(e.mean()*100,2))
for th in [1,1.5,2,3]:
    x=d1[d1.relv>th]; e=ev(x); print('relv>',th,len(e),round(e.mean()*100,2),'se',round(e.std()/len(e)**.5*100,2))
