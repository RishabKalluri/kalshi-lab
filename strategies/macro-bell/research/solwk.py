import pandas as pd, numpy as np
def fee(p): return 0.07*p*(1-p)
d=pd.read_parquet('research/data/KXSOL15M.parquet'); d=d[d.close<'2026-09-01'].copy()
ny=d.close.dt.tz_convert('America/New_York'); d['wk']=ny.dt.dayofweek>=5; d['m']=ny.dt.strftime('%m')
def ud(x,lo,hi):
    a=x.dropna(subset=['next_ask']); a=a[(a.next_ask>lo)&(a.next_ask<hi)]
    b=x.dropna(subset=['next_bid']); b=b[(1-b.next_bid>lo)&(1-b.next_bid<hi)]
    return pd.concat([a.y-a.next_ask-fee(a.next_ask),(1-b.y)-(1-b.next_bid)-fee(1-b.next_bid)])
for lab,x in [('weekend',d[d.wk]),('weekday',d[~d.wk])]:
  for hs in [(480,600),(240,360),(60,180)]:
    y=x[x.h.isin(hs)]
    for lo,hi in [(.05,.3),(.3,.5),(.5,.8),(.8,.97)]:
        e=ud(y,lo,hi); print(lab,hs,lo,hi,len(e),round(e.mean()*100,2),'se',round(e.std()/len(e)**.5*100,2))
