import pandas as pd, numpy as np, datetime as dt
from kalshi_lab.data.flow import FLOW
out=[]
for src in ('binance_solusdt',):
    for p in sorted((FLOW/src).glob('*.parquet')):
        day=dt.date.fromisoformat(p.stem)
        if day>=dt.date(2026,9,1): continue
        f=pd.read_parquet(p,columns=['t','buy','sell','n'])
        f['slot']=(f.t-1)//900*900
        g=f.groupby('slot').agg(buy=('buy','sum'),sell=('sell','sum'),n=('n','sum'))
        out.append(g)
a=pd.concat(out); a=a[~a.index.duplicated()]
a.to_parquet('/tmp/sol_slots.parquet'); print(a.shape)
