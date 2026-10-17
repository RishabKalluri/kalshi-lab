import numpy as np, pandas as pd
from scipy.stats import norm
o=pd.read_parquet('/tmp/sol_perp.parquet')
o=o[o.mid.between(0.05,0.95)]
sig=o.rv_60m*np.sqrt(o.h)
z=o.D/sig
o['sig']=norm.pdf(z)*(o.dev*o.S/1e4)/sig
o['res']=o.y-o.mid
print('corr res~sig',np.corrcoef(o.sig,o.res)[0,1], len(o))
print(o.groupby('h').apply(lambda g: pd.Series({'corr':np.corrcoef(g.sig,g.res)[0,1],'n':len(g)})))
fee=lambda p:0.07*p*(1-p)
for thr in [0.02,0.04,0.06,0.1]:
    for side in ['buy','sell']:
        if side=='buy': s=(o.sig>thr)&o.next_ask.notna(); pnl=(o.y-o.next_ask-fee(o.next_ask))[s]
        else: s=(o.sig<-thr)&o.next_bid.notna(); pnl=(o.next_bid-o.y-fee(o.next_bid))[s]
        x=o[s].assign(pnl=pnl)
        for half,m in [('A',x.close<'2026-05-01'),('B',x.close>='2026-05-01')]:
            y=x[m]
            print(thr,side,half,len(y),'%.2f'%(100*y.pnl.mean()),'se %.2f'%(100*y.pnl.std()/max(len(y),1)**.5))
