import pickle, numpy as np
D="/srv/kalshi/strategies/xrp-tiemodel/research/data"
o=pickle.load(open(f"{D}/est.pkl","rb")); est=o['est']; rows=o['rows']; SS=o['SS']
ev=np.array([r['ev'] for r in rows]); K=np.array([r['K'] for r in rows]); y=(ev>=K-1e-9).astype(float)
print("YES rate",y.mean(), "tie rate", (abs(ev-K)<1e-9).mean())
# empirical residual pools per s
res={s:(ev-est[s]) for s in SS}
def pyes(i,s):
    e=res[s]; m=~np.isnan(e)
    x=est[s][i]
    if np.isnan(x): return np.nan
    # P(ev>=K) = P(e >= K-x)
    return (e[m]>=K[i]-x-1e-9).mean()
# model accuracy at each s: Brier
for s in SS:
    p=np.array([pyes(i,s) for i in range(0,len(rows),7)]); yy=y[::7]; m=~np.isnan(p)
    print(s,"brier model %.4f"%((p[m]-yy[m])**2).mean(), "n",m.sum(), "ties frac %.3f"%(abs(ev-K)[::7][m]<1e-9).mean())
# trade-level
def fee(p): return 0.07*p*(1-p)
out=[]
for i,r in enumerate(rows):
    seen=set()
    for (t,price,tk,c) in sorted(r['tr']):
        s=r['close']-t
        if s<3 or s>45: continue
        sg=min([x for x in SS if x>=s]) if s<=45 else None
        if sg is None: continue
        p=pyes(i,sg) if True else None
        if np.isnan(p): continue
        if tk==1: side='Y'; cost=price; win=y[i]; pm=p     # taker bought YES at price
        else:     side='N'; cost=1-price; win=1-y[i]; pm=1-p  # NO ask = 1 - yes bid
        out.append((i,s,side,cost,win,pm,c))
import pandas as pd
df=pd.DataFrame(out,columns=['i','s','side','cost','win','pm','c'])
df['edge_model']=df.pm-df.cost
df['pnl']=df.win-df.cost-df.cost.apply(fee)
df.to_pickle(f"{D}/trades_eval.pkl")
print(len(df))
df['bin']=pd.cut(df.edge_model,[-1,-.3,-.15,-.05,0,.05,.1,.15,.25,.4,1])
print(df.groupby('bin').agg(n=('pnl','size'),pnl=('pnl','mean'),win=('win','mean'),pm=('pm','mean'),cost=('cost','mean')))
