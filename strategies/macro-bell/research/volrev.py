import pandas as pd, numpy as np
from kalshi_lab.data.flow import load_flow
# 15-min Binance SOL volume per window (dev months only), months loaded one at a time
rows=[]
for m in pd.period_range('2026-01','2026-08',freq='M'):
    s=str(m.start_time.date()); e=str((m.end_time+pd.Timedelta(seconds=1)).date())
    f=load_flow('binance_solusdt',s,e)
    cols=[c for c in f.columns]
    if not rows: print(cols)
    f['ts']=pd.to_datetime(f['t'],unit='s',utc=True)
    f['vol']=f[[c for c in cols if 'buy' in c or 'sell' in c][:2]].sum(axis=1)
    g=f.set_index('ts').vol.resample('15min',label='left',closed='right').sum()
    rows.append(g)
v=pd.concat(rows); v=v[~v.index.duplicated()]
v.to_frame('vol').to_parquet('/tmp/solvol15.parquet'); print(len(v))
