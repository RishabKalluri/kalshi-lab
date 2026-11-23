import pickle, numpy as np, datetime as dt
from math import erf, sqrt
D="/srv/kalshi/strategies/xrp-tiemodel/research/data"
rows=pickle.load(open(f"{D}/markets.pkl","rb")); spot=pickle.load(open(f"{D}/spot.pkl","rb"))
rows=sorted(rows,key=lambda r:r['close'])
T0={}
def arr(ts):
    d=dt.datetime.fromtimestamp(ts,dt.timezone.utc).strftime("%Y-%m-%d")
    if d not in T0: T0[d]=dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()
    return spot.get(d), int(ts-T0[d])
def window(close):
    a,i=arr(close)
    if a is None or i<62 or i>86399: return None
    w=a[i-60:i].copy()
    if np.isnan(w).sum()>3: return None
    m=np.nanmean(w); w[np.isnan(w)]=m   # fill
    return w
W=[window(r['close']) for r in rows]
cl=np.array([r['close'] for r in rows])
ratio=np.array([ (r['ev']/w.mean()) if w is not None else np.nan for r,w in zip(rows,W)])
SS=[2,3,5,8,12,20,30,45]
est={s:np.full(len(rows),np.nan) for s in SS}
for i,(r,w) in enumerate(zip(rows,W)):
    if w is None or i<4 or cl[i]-cl[i-4]>3601: continue
    b=np.nanmean(ratio[i-4:i])
    if np.isnan(b): continue
    for s in SS:
        # known seconds: first 60-s entries are at/before close-s ; remaining use last known price
        k=60-s
        v=(w[:k].sum()+w[k-1]*s)/60
        est[s][i]=v*b
ev=np.array([r['ev'] for r in rows]); K=np.array([r['K'] for r in rows])
print("sd of (ev-est) in ticks by s")
for s in SS:
    e=(ev-est[s]); m=~np.isnan(e)
    print(s, m.sum(), "sd %.2f ticks, mean %.2f, median abs %.2f"%(e[m].std()*1e4, e[m].mean()*1e4, np.median(abs(e[m]))*1e4))
pickle.dump(dict(est=est,rows=rows,SS=SS),open(f"{D}/est.pkl","wb"))
