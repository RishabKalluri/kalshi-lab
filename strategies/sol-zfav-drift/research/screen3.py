"""Screen 3: jump vs drift composition of the displacement at zfav fill time (SOL 1s Binance, since window open)."""
import io, json, numpy as np, pandas as pd, zstandard
d=pd.read_csv('/srv/kalshi/strategies/sol-zfav-beta/research/screen2.csv'); d['t']=pd.to_datetime(d.t,utc=True,format='mixed')
d['ts']=d.t.astype('datetime64[ns, UTC]').astype('int64')//10**9; d['day']=d.t.dt.strftime('%Y-%m-%d')
cache={}
def arr(day):
    if day in cache: return cache[day]
    if len(cache)>6: cache.clear()
    a=np.full(86400,np.nan)
    for l in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(open(f'/srv/kalshi-data/backfill/spot/binance_solusdt/{day}.jsonl.zst','rb'))):
        j=json.loads(l); a[(j['t']//10**9)%86400]=j['m']['price']
    cache[day]=pd.Series(a).ffill().values; return cache[day]
rows=[]
for r in d.itertuples():
    a=arr(r.day); e=r.ts%86400; o=e-int(900-r.tau) if False else None
    # window open = close-900 ; tau known => open = ts + tau - 900
    o=int(r.ts+r.tau-900)%86400
    if o>e: rows.append((np.nan,)*3); continue
    seg=a[o:e+1]
    dd=np.diff(np.log(seg)); tot=seg[-1]/seg[0]
    r10=np.log(seg[10:]/seg[:-10]) if len(seg)>20 else np.array([0.])
    k=np.abs(r10).argmax(); big=r10[k]
    rows.append((abs(big)/(abs(np.log(tot))+1e-9)*np.sign(big)*np.sign(np.log(tot)), (len(r10)-k)/60, np.abs(dd).max()/(np.sqrt((dd**2).sum())+1e-12)))
x=pd.DataFrame(rows,columns=['jfrac','age_min','maxshare'],index=d.index); d=pd.concat([d,x],axis=1); d.to_csv('/srv/kalshi/strategies/sol-zfav-beta/research/screen3.csv',index=False)
def agg(g): return pd.Series({'n':len(g),'c':g.pnl.sum()/g.q.sum()*100,'se':(g.pnl/g.q*100).std()/np.sqrt(len(g))})
for c in ('jfrac','age_min','maxshare'):
    y=d.dropna(subset=[c]); print(c); print(y.groupby(pd.qcut(y[c],5,duplicates='drop'),observed=True).apply(agg).round(2))
