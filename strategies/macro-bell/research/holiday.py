import pandas as pd, numpy as np
hol=['2026-01-01','2026-01-19','2026-02-16','2026-04-03','2026-05-25','2026-06-19','2026-07-03','2026-07-04']
for c in ['BTC','ETH','SOL','XRP','DOGE']:
    d=pd.read_parquet(f'research/data/KX{c}15M.parquet'); d=d[(d.close<'2026-09-01')&(d.h==480)].dropna(subset=['rv_fut','iv'])
    ny=(d.close.dt.tz_convert('America/New_York')).dt
    d['date']=d.close.dt.tz_convert('America/New_York').dt.strftime('%Y-%m-%d')
    d['wk']=d.close.dt.tz_convert('America/New_York').dt.dayofweek>=5
    d['r']=d.rv_fut/d.iv
    h=d[d.date.isin(hol)&~d.wk]; n=d[~d.date.isin(hol)&~d.wk]
    print(c,'holiday n',len(h),round(h.r.median(),3),'weekday',round(n.r.median(),3),'weekend',round(d[d.wk].r.median(),3))
