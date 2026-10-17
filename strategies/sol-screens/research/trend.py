import pandas as pd, numpy as np, sys
d=pd.read_parquet('research/data/KXSOL15M.parquet')
o=d[d.h==840].copy().sort_values('close')
o['open']=o.close-pd.Timedelta(minutes=15)
K=o.set_index('open').K
K=K[~K.index.duplicated()]
grid=pd.date_range(K.index.min(),K.index.max(),freq='15min')
Kg=K.reindex(grid)
lg=np.log(Kg)
r1=lg.diff()
vol=r1.rolling(96*3,min_periods=100).std().shift(1)  # per-window std, trailing 3d
feat=pd.DataFrame(index=grid)
for n in (2,4,8,16,32):
    feat[f'z{n}']=(lg-lg.shift(n))/(vol*np.sqrt(n))   # trend ending at this open (strike known at open)
o=o.set_index('open').join(feat,how='left')
o=o[~o.index.duplicated()]
def fee(p): return 0.07*p*(1-p)
o['half']=np.where(o.index<'2026-05-01',0,1)
o.to_pickle('/tmp/sol_trend.pkl')
def tab(f,bins,sub=None):
    rows=[]
    for lo,hi in bins:
        s=o[(o[f]>lo)&(o[f]<=hi)]
        for h in (0,1):
            t=s[s.half==h]
            a=t.dropna(subset=['next_ask']); b=t.dropna(subset=['next_bid'])
            py=(a.y-a.next_ask-fee(a.next_ask)); pn=((1-b.y)-(1-b.next_bid)-fee(1-b.next_bid))
            rows.append((f,lo,hi,h,len(t),round(t.y.mean(),3),round(py.mean()*100,2),round(pn.mean()*100,2)))
    return rows
R=[]
for f in ['z2','z4','z8','z16','z32']:
    R+=tab(f,[(-9,-2),(-2,-1.25),(1.25,2),(2,9)])
print(pd.DataFrame(R,columns='f lo hi half n ymean buyYES buyNO'.split()).to_string())
