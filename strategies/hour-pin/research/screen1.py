import pandas as pd, numpy as np, sys
from math import erf
from scipy.stats import norm
coin=sys.argv[1]
d=pd.read_parquet(f'research/data/{coin}.parquet')
d=d[d.close<'2026-09-01'].copy()
d['month']=d.close.dt.strftime('%m')
# fair value: lognormal, sigma = rv_15m blend, drift 0, D=S-K-basis? D already spot-strike adjusted
sig=(0.5*d.rv_15m+0.5*d.rv_60m).clip(lower=1e-5)   # per-sqrt-second vol assumed (check scale)
z=d.D/ d.S/(sig*np.sqrt(d.h))
d['p']=norm.cdf(z)
print(coin,len(d),'scale check: corr(p,y)',np.corrcoef(d.p,d.y)[0,1],'corr(mid,y)',np.corrcoef(d.mid,d.y)[0,1])
fee=lambda p:0.07*p*(1-p)
res=[]
for side in ('buy','sell'):
    if side=='buy':
        px=d.next_ask; edge=d.y-px-fee(px); sig_=d.p-px
    else:
        px=d.next_bid; edge=px-d.y-fee(px); sig_=px-d.p
    d['e_'+side]=edge; d['s_'+side]=sig_
x=d[d.h.between(60,600)]
x=x.assign(nq=pd.qcut(x.n_trades,4,labels=False,duplicates='drop'))
for side in ('buy','sell'):
    for thr in (0.05,0.10):
        m=x[(x['s_'+side]>thr)]
        print(side,thr,'all',round(m['e_'+side].mean()*100,2),len(m),'| by n_trades quartile',[ (round(g['e_'+side].mean()*100,2),len(g)) for _,g in m.groupby('nq')])
