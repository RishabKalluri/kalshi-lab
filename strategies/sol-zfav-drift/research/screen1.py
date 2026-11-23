"""Screen: do sol-zfav-maker fills differ when BTC/ETH moved with SOL (market-wide) vs SOL alone (idiosyncratic)?
Uses dev walk-forward fills (Jan-Sep) of sol-zfav-maker + 1s Binance spot. Output: research/screen1.csv + summary."""
import glob, io, json, sys, numpy as np, pandas as pd, zstandard
R='/srv/kalshi/results/sol-zfav-maker-1102-013957-wf-'
def day_arr(coin, day):
    p=f'/srv/kalshi-data/backfill/spot/binance_{coin}usdt/{day}.jsonl.zst'
    a=np.full(86400,np.nan)
    try: f=open(p,'rb')
    except FileNotFoundError: return a
    for l in io.TextIOWrapper(zstandard.ZstdDecompressor().stream_reader(f)):
        j=json.loads(l); t=j['t']//10**9; a[t%86400]=j['m']['price']
    s=pd.Series(a).ffill().values
    return s
rows=[]
for mdir in sorted(glob.glob(R+'2026-??')):
    fl=pd.read_csv(mdir+'/fills.csv',parse_dates=['time']); mk=pd.read_csv(mdir+'/markets.csv',parse_dates=['close_time','open_time'])
    mk=mk[mk.fills>0].set_index('ticker')
    fl['q']=fl.qty
    g=fl.groupby('ticker').agg(t=('time','first'),q=('q','sum'),tag=('tag','first'),px=('price','mean'))
    g=g.join(mk[['pnl','open_time','close_time','strike']],how='inner')
    cache={}
    for tk,r in g.iterrows():
        day=r.t.strftime('%Y-%m-%d'); od=r.open_time.strftime('%Y-%m-%d')
        if od!=day: continue
        for c in ('sol','btc','eth'):
            if (c,day) not in cache: cache[(c,day)]=day_arr(c,day)
        ts=int(r.t.timestamp()); o=int(r.open_time.timestamp())
        if ts%86400<o%86400: continue
        out={'ticker':tk,'month':mdir[-7:],'t':r.t,'tau':(r.close_time-r.t).total_seconds(),'q':r.q,'pnl':r.pnl,'dir':1 if r.tag=='zm-yes' else -1,'px':r.px}
        for c in ('sol','btc','eth'):
            a=cache[(c,day)]; out['r_'+c]=np.log(a[ts%86400]/a[o%86400])
            out['r60_'+c]=np.log(a[ts%86400]/a[(ts-60)%86400]) if ts%86400>=60 else np.nan
        rows.append(out)
d=pd.DataFrame(rows); d.to_csv('/srv/kalshi/strategies/sol-zfav-beta/research/screen1.csv',index=False); print(len(d))
