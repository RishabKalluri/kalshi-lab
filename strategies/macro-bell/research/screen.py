import pandas as pd, numpy as np
ev830=['2026-01-09','2026-01-13','2026-01-14','2026-01-30','2026-02-11','2026-02-13','2026-02-27','2026-03-06','2026-03-11','2026-03-18','2026-04-03','2026-04-10','2026-04-14','2026-05-08','2026-05-12','2026-05-13','2026-06-05','2026-06-10','2026-06-11','2026-07-02','2026-07-14','2026-07-15','2026-08-07','2026-08-12','2026-08-13']
ev1400=['2026-01-28','2026-03-18','2026-04-29','2026-06-17','2026-07-29']
def fee(p): return 0.07*p*(1-p)
out=[]
for c in ['BTC','ETH','SOL','XRP','DOGE']:
    d=pd.read_parquet(f'research/data/KX{c}15M.parquet')
    d=d[d.close<'2026-09-01'].copy(); d['coin']=c; out.append(d)
d=pd.concat(out)
ny=d.close.dt.tz_convert('America/New_York'); op=ny-pd.Timedelta(minutes=15)
d['openhm']=op.dt.hour*60+op.dt.minute; d['date']=op.dt.strftime('%Y-%m-%d')
def sel(evs,hm): return d[(d.openhm==hm)&d.date.isin(evs)]
for name,s,ctrl in [('8:30 events',sel(ev830,510),d[(d.openhm==510)&~d.date.isin(ev830)]),('14:00 FOMC',sel(ev1400,840),d[(d.openhm==840)&~d.date.isin(ev1400)])]:
    for lab,x in [('event',s),('control',ctrl)]:
        x=x[x.h==840].dropna(subset=['rv_fut','iv'])
        print(name,lab,'n mkts',len(x),'median rv_fut/iv',round((x.rv_fut/x.iv).median(),2),'mean rv_fut/rv_15m',round((x.rv_fut/x.rv_15m).mean(),2))
    # underdog edge
    for lab,x in [('event',s),('control',ctrl)]:
        for h in (720,840):
            y=x[x.h==h]
            a=y.dropna(subset=['next_ask']); a=a[(a.next_ask>.1)&(a.next_ask<.45)]
            b=y.dropna(subset=['next_bid']); b=b[(1-b.next_bid>.1)&(1-b.next_bid<.45)]
            ev=np.r_[a.y-a.next_ask-fee(a.next_ask),(1-b.y)-(1-b.next_bid)-fee(1-b.next_bid)]
            print(name,lab,h,'underdog n',len(ev),'mean c',round(ev.mean()*100,2) if len(ev) else None,'se',round(ev.std()/np.sqrt(max(len(ev),1))*100,2) if len(ev) else None)
