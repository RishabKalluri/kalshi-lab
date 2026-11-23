import pickle, numpy as np, datetime as dt
D="/srv/kalshi/strategies/xrp-tiemodel/research/data"
rows=pickle.load(open(f"{D}/markets.pkl","rb")); spot=pickle.load(open(f"{D}/spot.pkl","rb"))
def arr(ts):
    d=dt.datetime.fromtimestamp(ts,dt.timezone.utc).strftime("%Y-%m-%d")
    return spot.get(d), int(ts-dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp())
def avg(close, off):  # mean of seconds [close-60+off, close-1+off]
    a,i=arr(close)
    if a is None or i-60+off<0 or i+off>86400: return np.nan
    w=a[i-60+off:i+off]
    if np.isnan(w).sum()>3: return np.nan
    return np.nanmean(w)
for off in [-2,-1,0,1,2]:
    e=np.array([ (avg(r['close'],off)-r['ev']) for r in rows]); e=e[~np.isnan(e)]
    print(off, len(e), "mean %.5f sd %.5f mad %.5f"%(e.mean(), e.std(), np.median(abs(e-np.median(e)))))
print("--- basis tracking")
rows=sorted(rows,key=lambda r:r['close'])
d=np.array([avg(r['close'],0)-r['ev'] for r in rows])
cl=np.array([r['close'] for r in rows])
# previous markets (consecutive 900s apart) 
for n in [1,2,4,8,16]:
    errs=[]
    for i in range(n,len(rows)):
        if cl[i]-cl[i-n]>900*n+1: continue
        b=np.nanmean(d[i-n:i])
        if np.isnan(b) or np.isnan(d[i]): continue
        errs.append(d[i]-b)
    e=np.array(errs); print(n,len(e),"sd %.5f mad %.5f"%(e.std(), np.median(abs(e-np.median(e)))), "frac |e|<0.00005: %.3f"%(abs(e)<5e-5).mean())
# short term-lag dependence: returns of basis
