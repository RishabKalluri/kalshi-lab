import pandas as pd, numpy as np
d=pd.read_parquet('research/data/KXSOL15M.parquet')
def fee(p): return 0.07*p*(1-p)
d['half']=np.where(d.close<'2026-05-01',0,1)
a=d.dropna(subset=['next_ask']).copy(); a['ev']=a.y-a.next_ask-fee(a.next_ask); a['pc']=(a.next_ask*100).round()
b=d.dropna(subset=['next_bid']).copy(); b['ev']=(1-b.y)-(1-b.next_bid)-fee(1-b.next_bid); b['pc']=((1-b.next_bid)*100).round()
x=pd.concat([a.assign(side='yes'),b.assign(side='no')])
x['band']=pd.cut(x.pc,[0,5,10,20,30,40,50,60,70,80,90,95,100])
t=x.groupby(['band','half'],observed=True).ev.agg(['mean','count']).unstack()
print((t*[100,100,1,1]).round(2) if False else t.round(4))
# time horizon x band
x['hb']=pd.cut(x.h,[0,100,200,400,700,900])
print(x[x.pc>=85].groupby(['hb','half'],observed=True).ev.agg(['mean','count']).unstack().round(4))
