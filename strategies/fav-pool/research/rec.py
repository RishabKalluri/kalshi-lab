import pandas as pd, numpy as np
fee=lambda p:0.07*p*(1-p)
R=[]
for s in ('KXBTC15M','KXETH15M','KXSOL15M','KXXRP15M','KXDOGE15M'):
    d=pd.read_parquet(f'research/data/{s}.parquet'); d=d[d.close>='2026-06-01'].copy(); d['s']=s
    a=d.dropna(subset=['next_ask']).copy(); a['ev']=a.y-a.next_ask-fee(a.next_ask); a['pc']=(a.next_ask*100); a['side']='yes'
    b=d.dropna(subset=['next_bid']).copy(); b['ev']=(1-b.y)-(1-b.next_bid)-fee(1-b.next_bid); b['pc']=(1-b.next_bid)*100; b['side']='no'
    R+= [a[['s','h','ev','pc','side','close']],b[['s','h','ev','pc','side','close']]]
x=pd.concat(R); x['band']=pd.cut(x.pc,[0,10,20,30,40,50,60,70,80,90,95,100]); x['hb']=pd.cut(x.h,[0,120,300,600,900])
x['mo']=x.close.dt.month
t=x.groupby(['band','hb'],observed=True).ev.agg(['mean','count']); t['se']=x.groupby(['band','hb'],observed=True).ev.sem()
t['t']=t['mean']/t.se
print((t[t['count']>500]*[100,1,100,1]).round(2).sort_values('t').tail(8))
print((t[t['count']>500]*[100,1,100,1]).round(2).sort_values('t').head(6))
print(x.groupby('s').ev.mean().round(4)*100)
