import pandas as pd, numpy as np
fee=lambda p:0.07*p*(1-p)
R=[]
for s in ('KXBTC15M','KXETH15M','KXSOL15M','KXXRP15M','KXDOGE15M'):
    d=pd.read_parquet(f'research/data/{s}.parquet'); d['s']=s
    a=d.dropna(subset=['next_ask']).copy(); a['ev']=a.y-a.next_ask-fee(a.next_ask); a['pc']=a.next_ask*100; a['side']='yes'
    b=d.dropna(subset=['next_bid']).copy(); b['ev']=(1-b.y)-(1-b.next_bid)-fee(1-b.next_bid); b['pc']=(1-b.next_bid)*100; b['side']='no'
    R+=[a[['s','h','ev','pc','side','close','ticker']],b[['s','h','ev','pc','side','close','ticker']]]
x=pd.concat(R); x['mo']=x.close.dt.month
f=x[(x.pc>90)&(x.pc<=95)&(x.h>=300)&(x.h<=720)]
print(f.groupby('mo').ev.agg(['mean','count']).round(4).T)
print(f.groupby(['s',f.mo>=6]).ev.agg(['mean','count']).round(4).unstack())
# one per market (first horizon h largest) to mimic one trade/market
g=f.sort_values('h',ascending=False).groupby('ticker').head(1)
print(len(g), g.ev.mean(), g.ev.sem(), g[g.mo>=6].ev.mean(), len(g[g.mo>=6]))
print(g.groupby(['mo']).ev.agg(['mean','count']).round(4).T)
print(g.groupby('side').ev.agg(['mean','count']))
x2=x[(x.pc>95)&(x.h>=120)&(x.h<=600)].sort_values('h',ascending=False).groupby('ticker').head(1); print('95-100', x2[x2.mo>=6].ev.agg(['mean','count','sem']))
