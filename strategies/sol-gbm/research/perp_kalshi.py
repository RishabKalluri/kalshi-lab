import numpy as np, pandas as pd
from kalshi_lab.data.flow import load_flow
d=pd.read_parquet('research/data/KXSOL15M.parquet')
d=d[d.h<=300].copy()
d['ts']=(d.close.astype('datetime64[s, UTC]').astype('int64') - d.h)
d['day']=d.close.dt.strftime('%Y-%m-%d')
devs=[]
for day,g in d.groupby(d.close.dt.floor('D')):
    a=(day-pd.Timedelta(days=0)).strftime('%Y-%m-%d'); b=(day+pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    try: p=load_flow('okx_solusdtswap',a,b); s=load_flow('binance_solusdt',a,b)
    except Exception: continue
    if len(p)<1000 or len(s)<1000: continue
    t0=min(p.t.min(),s.t.min())-1200; idx=np.arange(t0,t0+86400+1300)
    P=p.drop_duplicates('t').set_index('t').px.reindex(idx).ffill(); S=s.drop_duplicates('t').set_index('t').px.reindex(idx).ffill()
    dev=np.log(P/S); dev=dev-dev.rolling(900,min_periods=300).mean()
    # smooth over last 3 s
    dev=dev.rolling(3).mean()
    x=g.copy(); x['dev']=dev.reindex(x.ts.values).values*1e4
    devs.append(x)
o=pd.concat(devs).dropna(subset=['dev','D','rv_60m'])
o.to_parquet('/tmp/sol_perp.parquet')
print(len(o), o.close.min())
