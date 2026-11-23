"""Screen 4: path efficiency (drift vs chop) since window open as a predictor of outcome-minus-price, all z, SOL.
Row = dataset market x horizon; ER = |net log move| / sum |1s moves| since open, jump share, signed by direction of D."""
import io, json, numpy as np, pandas as pd, zstandard
d=pd.read_parquet('/srv/kalshi/research/data/KXSOL15M.parquet'); d=d[d.close<'2026-09-01'].copy()
print(d.h.value_counts().sort_index().to_dict())
d=d[d.h.isin([300,360,480])&(d.close>='2026-03-01')]
d['day']=(d.close-pd.Timedelta(seconds=1)).dt.strftime('%Y-%m-%d')
cache={}
def arr(day):
    if day not in cache:
        cache.clear(); a=np.full(86400,np.nan)
        try:
            for l in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(f'/srv/kalshi-data/backfill/spot/binance_solusdt/{day}.jsonl.zst','rb'))):
                j=json.loads(l); a[(j['t']//10**9)%86400]=j['m']['price']
        except FileNotFoundError: pass
        cache[day]=pd.Series(a).ffill().values
    return cache[day]
out=[]
for r in d.sort_values('close').itertuples():
    a=arr(r.day); c=int(r.close.timestamp())%86400; e=c-r.h; o=c-900
    if o<0 or e<=o+30 or np.isnan(a[o]): out.append((np.nan,np.nan)); continue
    seg=a[o:e+1]; dd=np.abs(np.diff(np.log(seg))); net=abs(np.log(seg[-1]/seg[0]))
    out.append((net/(dd.sum()+1e-12), 0 if net==0 else dd.max()/net))
d=d.sort_values('close'); d[['er','mx']]=out
d['sgn']=np.sign(d.D); d['yy']=d.y.where(d.sgn>0,1-d.y)  # outcome in direction of the current displacement
d['ask_d']=np.where(d.sgn>0,d.ask,1-d.bid)            # price to buy the displaced side
d['gain']=d.yy-d.ask_d
d['z']=d.D.abs()/(d.S*d.rv_15m*np.sqrt(d.h/900))
d.to_parquet('/srv/kalshi/strategies/sol-zfav-drift/research/screen4.parquet')
for zlo,zhi in ((0.5,1.0),(1.0,1.5),(1.5,9)):
    x=d[(d.z>=zlo)&(d.z<zhi)].dropna(subset=['er'])
    print('z',zlo,zhi,len(x)); print(x.groupby(pd.qcut(x.er,5),observed=True).gain.agg(['count','mean','sem']).mul([1,100,100]).round(2))
