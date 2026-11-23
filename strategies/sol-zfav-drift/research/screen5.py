"""Screen 5: does previous-window path efficiency / jump share split the open reversal vs continuation? SOL, h=840 rows,
taker at next real fill incl. fee. R = log move of previous 15m window (spot, open to close)."""
import io, json, numpy as np, pandas as pd, zstandard
d=pd.read_parquet('/srv/kalshi/research/data/KXSOL15M.parquet'); d=d[(d.h==840)&(d.close<'2026-09-01')&(d.close>='2026-02-01')].sort_values('close').copy()
cache={}
def arr(day):
    if day not in cache:
        if len(cache)>3: cache.clear()
        a=np.full(86400,np.nan)
        try:
            for l in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(f'/srv/kalshi-data/backfill/spot/binance_solusdt/{day}.jsonl.zst','rb'))):
                j=json.loads(l); a[(j['t']//10**9)%86400]=j['m']['price']
        except FileNotFoundError: pass
        cache[day]=pd.Series(a).ffill().values
    return cache[day]
out=[]
for r in d.itertuples():
    o=r.close-pd.Timedelta(seconds=900); s0=o-pd.Timedelta(seconds=900)
    if s0.date()!=(o-pd.Timedelta(seconds=1)).date(): out.append((np.nan,)*3); continue
    a=arr(s0.strftime('%Y-%m-%d')); i0=int(s0.timestamp())%86400; i1=int(o.timestamp())%86400-1
    seg=a[i0:i1+1]
    if len(seg)<800 or np.isnan(seg[0]): out.append((np.nan,)*3); continue
    dd=np.diff(np.log(seg)); R=np.log(seg[-1]/seg[0]); r10=np.log(seg[10:]/seg[:-10]); k=np.abs(r10).argmax()
    out.append((R, abs(R)/(np.abs(dd).sum()+1e-12), abs(r10[k])/(abs(R)+1e-9)*(1 if r10[k]*R>0 else -1)))
d[['R','er','jf']]=out; d=d.dropna(subset=['R']); d['ar']=d.R.abs()/ (d.rv_15m.where(d.rv_15m>0))
d.to_parquet('/srv/kalshi/strategies/sol-zfav-drift/research/screen5.parquet')
dirn=np.sign(d.R)   # +1: previous window went up
# fade: bet against dirn
px_fade=np.where(dirn>0,1-d.next_bid,d.next_ask); y_fade=np.where(dirn>0,1-d.y,d.y)
px_fol=np.where(dirn>0,d.next_ask,1-d.next_bid); y_fol=np.where(dirn>0,d.y,1-d.y)
fee=lambda p: np.ceil(0.07*p*(1-p)*100)/100
d['fade']=(y_fade-px_fade-fee(px_fade))*100; d['fol']=(y_fol-px_fol-fee(px_fol))*100
d=d.dropna(subset=['fade'])
big=d[d.ar>=d.ar.quantile(0.5)]
print('n',len(d),len(big))
for key in ('er','jf'):
    print(key); print(big.groupby(pd.qcut(big[key],4,duplicates='drop'),observed=True)[['fade','fol']].agg(['count','mean','sem']).round(2))
