import pickle, numpy as np, pandas as pd
D="/srv/kalshi/strategies/xrp-tiemodel/research/data"
o=pickle.load(open(f"{D}/est.pkl","rb")); est=o['est']; rows=o['rows']
ev=np.array([r['ev'] for r in rows]); K=np.array([r['K'] for r in rows]); y=(ev>=K-1e-9).astype(float)
for s in [5,12,30]:
    d=(est[s]-K)*1e4; m=~np.isnan(d)
    b=pd.cut(d[m],[-100,-6,-3,-1.5,-0.5,0.5,1.5,3,6,100])
    print(s); print(pd.DataFrame({'y':y[m],'b':b}).groupby('b').y.agg(['mean','size']))
