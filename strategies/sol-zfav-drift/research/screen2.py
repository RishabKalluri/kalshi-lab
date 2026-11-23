"""Screen 2: flow filter on sol-zfav-maker dev fills. Signed (by favourite direction) taker imbalance over last 60/300 s
and trade intensity vs 1h baseline, Binance spot + OKX perp. Output: c/ct by quartile."""
import numpy as np, pandas as pd
d=pd.read_csv('/srv/kalshi/strategies/sol-zfav-beta/research/screen1.csv',)
d['t']=pd.to_datetime(d.t,utc=True,format='mixed')
d['day']=d.t.dt.strftime('%Y-%m-%d'); d['ts']=(d.t.astype('datetime64[ns, UTC]').astype('int64')//10**9)
cache={}
def load(src,day):
    k=(src,day)
    if k not in cache:
        if len(cache)>8: cache.clear()
        try: f=pd.read_parquet(f'/srv/kalshi-data/backfill/flow/{src}/{day}.parquet')
        except Exception: f=None
        cache[k]=f
    return cache[k]
out=[]
for i,r in d.iterrows():
    row={}
    for src,nm in (('binance_solusdt','b'),('okx_solusdtswap','o')):
        f=load(src,r.day)
        if f is None: continue
        t=f.t.values; lo=lambda w:np.searchsorted(t,r.ts-w,side='right'); hi=np.searchsorted(t,r.ts-1,side='right')
        for w in (60,300):
            a=lo(w); buy=f.buy.values[a:hi].sum(); sell=f.sell.values[a:hi].sum()
            row[f'{nm}_imb{w}']=r.dir*(buy-sell)/(buy+sell+1e-9)
            row[f'{nm}_vol{w}']=(buy+sell)
        a=lo(3600); row[f'{nm}_rel']=(f.buy.values[lo(300):hi].sum()+f.sell.values[lo(300):hi].sum())/300/((f.buy.values[a:hi].sum()+f.sell.values[a:hi].sum())/3600+1e-9)
    out.append(row)
d=pd.concat([d,pd.DataFrame(out,index=d.index)],axis=1); d.to_csv('/srv/kalshi/strategies/sol-zfav-beta/research/screen2.csv',index=False)
def agg(g): return pd.Series({'n':len(g),'c':g.pnl.sum()/g.q.sum()*100,'se':(g.pnl/g.q*100).std()/np.sqrt(len(g))})
for c in ['b_imb60','b_imb300','o_imb60','o_imb300','b_rel','o_rel']:
    x=d.dropna(subset=[c]); print(c); print(x.groupby(pd.qcut(x[c],4,duplicates='drop'),observed=True).apply(agg).round(2))
