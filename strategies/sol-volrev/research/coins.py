import pandas as pd, numpy as np, sys
from kalshi_lab.data.flow import load_flow
def fee(p): return 0.07*p*(1-p)
for c in ['ETH','BTC','XRP','DOGE']:
    src=f'binance_{c.lower()}usdt'
    rows=[]
    for m in pd.period_range('2026-01','2026-08',freq='M'):
        s=str(m.start_time.date()); e=str((m.end_time+pd.Timedelta(seconds=1)).date())
        try: f=load_flow(src,s,e)
        except Exception as ex: continue
        if len(f)==0: continue
        f['ts']=pd.to_datetime(f['t'],unit='s',utc=True); f['vol']=f.buy+f.sell
        rows.append(f.set_index('ts').vol.resample('15min',label='left',closed='right').sum())
    if not rows: print(c,'no flow'); continue
    v=pd.concat(rows); v=v[~v.index.duplicated()]
    rel=v/v.groupby(v.index.time).transform(lambda s: s.rolling(14,min_periods=7).median().shift(1))
    d=pd.read_parquet(f'research/data/KX{c}15M.parquet'); d=d[(d.close<'2026-09-01')&(d.h==840)].copy()
    d['close']=d.close.astype('datetime64[ns, UTC]'); d['open']=d.close-pd.Timedelta(minutes=15)
    k=d.set_index('open').K; kp=k.rename(index=lambda x:x+pd.Timedelta(minutes=15))
    d['Kprev']=d.open.map(kp); d['relv']=(d.open-pd.Timedelta(minutes=15)).map(rel)
    d['z1']=np.log(d.K/d.Kprev)/d.rv_15m
    d=d.dropna(subset=['z1','relv']); d=d[d.z1.abs()<d.z1.abs().quantile(.999)]
    d['z1']=d.z1/(1.4826*d.z1.abs().median()); d=d[d.z1.abs()>1.25]
    d['half']=np.where(d.close<'2026-05-01',0,1)
    def ev(x):
        up=x.z1>0; n=x[up].dropna(subset=['next_bid']); y=x[~up].dropna(subset=['next_ask'])
        return np.r_[(1-n.y)-(1-n.next_bid)-fee(1-n.next_bid), y.y-y.next_ask-fee(y.next_ask)]
    for lab,x in [('relv<=1',d[d.relv<=1]),('1-2',d[(d.relv>1)&(d.relv<=2)]),('>2',d[d.relv>2])]:
        for h in (0,1):
            e=ev(x[x.half==h]); print(c,lab,'half',h,len(e),round(e.mean()*100,2) if len(e) else None,'se',round(e.std()/max(len(e),1)**.5*100,2) if len(e)>1 else None)
