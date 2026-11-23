import pandas as pd,numpy as np
exec(open('strategies/rain-obs/research/screen1.py').read().split("M=pd.read_pickle")[0])
D='strategies/rain-obs/research/data/'
fc={}
for c,s in st.items():
    f=pd.read_csv(D+f'fc_{s}.csv',skiprows=3);f.columns=['time','p1','prob1','p2'];f['time']=pd.to_datetime(f.time);fc[c]=f.set_index('time')
M=pd.read_pickle('/tmp/rain_M2.pkl');T=pd.read_pickle('/tmp/rain_T.pkl')
T=T.sort_values('t')
rows=[]
for _,r in M.iterrows():
    tt=T[T.ticker==r.ticker] if False else None
import collections
G={k:v for k,v in T.groupby('ticker')}
for _,r in M.iterrows():
    g=G.get(r.ticker)
    if g is None: continue
    for H in (3,6,12,18):
        dec=r.close_dt-pd.Timedelta(hours=H)
        dec_ns=pd.Timestamp(dec).value
        w=g[(g.t<=dec_ns)&(g.t>dec_ns-3600e9*1.5)]
        if len(w)==0: continue
        price=w.p.iloc[-1]
        seen=pd.notna(r.fr2) and r.fr2+pd.Timedelta(minutes=10)<=dec
        f=fc[r.city]; rem=f.loc[dec.floor('h')+pd.Timedelta(hours=1):r.close_dt.floor('h')]
        full=f.loc[r.close_dt.floor('h')-pd.Timedelta(hours=23):r.close_dt.floor('h')]
        rows.append(dict(ticker=r.ticker,city=r.city,H=H,price=price,yes=r.yes,seen=seen,rem_mm=rem.p1.sum(),rem_prob=rem.prob1.max(),rem_mm2=rem.p2.sum(),day_mm=full.p1.sum()))
R=pd.DataFrame(rows);R.to_pickle('/tmp/rain_R.pkl');print(len(R))
