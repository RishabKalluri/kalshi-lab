import pandas as pd, numpy as np
mk=pd.read_parquet('strategies/wx-fcmodel/research/data/mk.parquet'); tr=pd.read_parquet('strategies/wx-fcmodel/research/data/tr.parquet')
tr=tr.sort_values('t')
mk['ev_date']=mk.ev.str[-7:]
dates={}
import datetime as dt
def pdate(s): return dt.datetime.strptime(s,'%y%b%d')
mk['d']=mk.ev_date.map(pdate)
# bracket midpoint
def mid(r):
    if r.st=='between': return (r.fl+r.cap)/2
    if r.st=='greater': return r.fl+1.5
    if r.st=='less': return r.cap-1.5
    return np.nan
mk['mu']=mk.apply(mid,axis=1)
tr=tr.merge(mk[['tk','ev','city','d','mu']],on='tk')
def implied(ev_df, t):
    g=ev_df[(ev_df.t<=t)&(ev_df.t>t-5400)]
    if g.tk.nunique()<4: return np.nan
    last=g.groupby('tk').agg(p=('p','last'),mu=('mu','first'))
    if last.p.sum()<=0: return np.nan
    return (last.p*last.mu).sum()/last.p.sum()
rows=[]
for (city,d),g in tr.groupby(['city','d']):
    base=(d-dt.datetime(1970,1,1)).total_seconds()
    r={'city':city,'d':d}
    for lab,h in (('t0',12),('t1',16),('t2',20)):
        r[lab]=implied(g, base+h*3600)
    rows.append(r)
m=pd.DataFrame(rows).dropna(); m.to_pickle('strategies/wx-xcity/research/implied.pkl')
w=m.pivot(index='d',columns='city',values=['t0','t1','t2'])
east=['NY','MIA']; west=['CHI','DAL','AUS','LAX','PHX']
for a in east:
    dA=(w['t1'][a]-w['t0'][a])
    for b in ['NY','MIA']+west:
        if b==a: continue
        dB=(w['t2'][b]-w['t1'][b]); ok=dA.notna()&dB.notna()
        print(a,'->',b,'n',ok.sum(),'corr',round(np.corrcoef(dA[ok],dB[ok])[0,1],3),'slope',round(np.polyfit(dA[ok],dB[ok],1)[0],3))
for b in east+west:
    dA=(w['t1'][b]-w['t0'][b]);dB=(w['t2'][b]-w['t1'][b]);ok=dA.notna()&dB.notna()
    print('own',b,ok.sum(),round(np.corrcoef(dA[ok],dB[ok])[0,1],3), 'sd dB',round(dB[ok].std(),2))
