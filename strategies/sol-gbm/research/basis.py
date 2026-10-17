import numpy as np, pandas as pd
from kalshi_lab.data.flow import load_flow
d=pd.read_parquet('research/data/KXSOL15M.parquet')
d=d[d.h==840].copy()
d['ts']=(d.close.astype('datetime64[s, UTC]').astype('int64') - d.h)
out=[]
prev=None
days=sorted(d.close.dt.floor('D').unique())
for day in days:
    day=pd.Timestamp(day)
    a=day.strftime('%Y-%m-%d'); b=(day+pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    try: p=load_flow('okx_solusdtswap',a,b); s=load_flow('binance_solusdt',a,b)
    except Exception: continue
    if len(p)<1000 or len(s)<1000: continue
    t0=int(day.timestamp())-3700; idx=np.arange(t0,t0+86400+3800)
    # need previous hour: load previous day tail
    pa=(day-pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        p=pd.concat([load_flow('okx_solusdtswap',pa,a),p]); s=pd.concat([load_flow('binance_solusdt',pa,a),s])
    except Exception: pass
    P=p.drop_duplicates('t').set_index('t').reindex(idx); S=s.drop_duplicates('t').set_index('t').reindex(idx)
    dev=np.log(P.px.ffill()/S.px.ffill())*1e4
    f=pd.DataFrame({'dev15':dev.rolling(900).mean(),'dev1h':dev.rolling(3600).mean(),'devnow':dev.rolling(60).mean(),
        'pimb15':((P.buy-P.sell).fillna(0)).rolling(900).sum()/((P.buy+P.sell).fillna(0).rolling(900).sum()+1),
        'pvol15':(P.buy+P.sell).fillna(0).rolling(900).sum(),'svol15':(S.buy+S.sell).fillna(0).rolling(900).sum(),
        'pn15':P.n.fillna(0).rolling(900).sum()})
    g=d[d.close.dt.floor('D')==day]
    x=g.join(f.reindex(g.ts.values).set_index(g.index))
    out.append(x)
o=pd.concat(out).dropna(subset=['dev15','dev1h','rv_60m'])
o['dd']=o.dev15-o.dev1h
o['ratio']=np.log(o.pvol15/(o.svol15+1)+1e-9)
o['zf']=o.move_fut/(o.rv_60m*np.sqrt(840))
o['lv']=np.log(o.rv_fut/o.rv_60m)
o['res']=o.y-o.mid
o['half']=np.where(o.close<'2026-05-01','A','B')
for c in ['dev15','dev1h','devnow','dd','pimb15','ratio','pn15']:
    print(c,[ (h,'zf %.3f lv %.3f res %.3f'%tuple(np.corrcoef(g[c],g[t])[0,1] for t in ['zf','lv','res'])) for h,g in o.groupby('half')])
