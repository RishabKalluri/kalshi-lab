import pickle, numpy as np, pandas as pd
from scipy import stats
D="/srv/kalshi/strategies/xrp-tiemodel/research/data"
o=pickle.load(open(f"{D}/est.pkl","rb")); est=o['est']; rows=o['rows']; SS=o['SS']
ev=np.array([r['ev'] for r in rows]); K=np.array([r['K'] for r in rows]); y=(ev>=K-1e-9).astype(float)
for s in [3,8,20,30]:
    e=ev-est[s]; m=~np.isnan(e)
    rel=(e/K)[m]
    # robust scale in bp
    q=np.percentile(rel,[2.5,16,50,84,97.5])*1e4
    print(s,"quantiles bp",np.round(q,2))
    for df_ in [3,5,10,1000]:
        # fit scale by MAD
        sc=np.median(abs(rel-np.median(rel)))/stats.t.ppf(0.75,df_)
        z=((est[s]-(K-0.5e-4))/K)[m]/sc
        p=stats.t.cdf(z,df_)
        pp=np.clip(p,1e-4,1-1e-4)
        ll=-(y[m]*np.log(pp)+(1-y[m])*np.log(1-pp)).mean()
        print("  t df",df_,"scale bp %.3f"%(sc*1e4),"logloss %.4f"%ll,"brier %.5f"%((p-y[m])**2).mean())
