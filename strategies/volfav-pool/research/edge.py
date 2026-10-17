import pandas as pd, numpy as np
from scipy.stats import norm
d = pd.read_parquet('/srv/kalshi/strategies/volfav-pool/research/trades.parquet')
d['fc']=d.iv/d.ratio
d['pm']=norm.cdf(np.abs(d.D)/(d.fc*np.sqrt(d.h-40)))
d['fee']=np.ceil(0.07*d.px*(1-d.px)*100)/100
d['pred']=(d.pm-d.px-d.fee)*100
d['pc']=d.pnl*100
d.to_parquet('/srv/kalshi/strategies/volfav-pool/research/trades2.parquet')
d['eb']=pd.cut(d.pred,[-100,-10,-5,-2,0,1,2,3,5,8,100])
g=d.groupby('eb',observed=True).agg(n=('pc','size'),pred=('pred','mean'),real=('pc','mean'),mk=('ticker','nunique'))
print(g.round(2))
for c,x in d.groupby('coin'):
    print(c, x.groupby('eb',observed=True).agg(n=('pc','size'),pred=('pred','mean'),real=('pc','mean')).round(2).T.to_string())
