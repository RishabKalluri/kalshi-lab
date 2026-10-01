import numpy as np, pandas as pd
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression
LOCK = pd.Timestamp("2026-08-20", tz="UTC"); SPLIT = pd.Timestamp("2026-05-01", tz="UTC")
H = [360, 300, 240, 180, 120, 90, 60]
EPS = norm.ppf((np.arange(40)+0.5)/40)
df = pd.read_parquet("research/data/KXSOL15M.parquet")
df = df[df.close < LOCK].dropna(subset=["rv_5m","rv_15m","rv_60m","rv_4h","rv_fut","D","mid"])
df = df[(df.rv_5m>0)&(df.rv_15m>0)&(df.rv_60m>0)&(df.rv_4h>0)].copy()
df["hour"]=df.close.dt.hour; df["vov"]=np.abs(np.log(df.rv_5m/df.rv_60m))
X = lambda d: np.column_stack([np.ones(len(d)), np.log(d.rv_5m), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h), *[(d.hour==hh).astype(float) for hh in range(1,24)], np.log(d.h)])
Zs = lambda d: np.column_stack([np.ones(len(d)), np.log(d.h), d.vov, np.log(d.rv_5m/d.rv_4h)])
tr = df[(df.close<SPLIT)&(df.rv_fut>0.0005)]
beta,*_ = np.linalg.lstsq(X(tr), np.log(tr.rv_fut), rcond=None)
res = np.log(tr.rv_fut)-X(tr)@beta
g,*_ = np.linalg.lstsq(Zs(tr), np.abs(res), rcond=None)
d = df[df.h.isin(H)&(df.mid>0.02)&(df.mid<0.98)].copy()
mu = X(d)@beta; s = np.clip(Zs(d)@g,0.05,1)*np.sqrt(np.pi/2)
tp = np.sqrt(np.maximum(d.h-40,5)).values
sig = np.exp(np.asarray(mu)[:,None]+np.asarray(s)[:,None]*EPS[None,:])
d["zmix"] = norm.ppf(np.clip(norm.cdf(d.D.values[:,None]/(sig*tp[:,None])).mean(1),1e-4,1-1e-4))
d["zpt"] = np.clip(d.D/(np.exp(mu)*tp),-8,8)
d["lm"] = np.log(d.mid/(1-d.mid))
d["half"]=np.where(d.close<SPLIT,"A","B")
for zc in ["zpt","zmix"]:
    F = lambda x: np.column_stack([x.lm, x[zc], x[zc]*np.log(x.h), x.lm*np.log(x.h)])
    A = d[d.half=="A"]
    lr = LogisticRegression(C=10, max_iter=1000).fit(F(A), A.y)
    print(zc, lr.coef_.round(3), lr.intercept_.round(3))
    for half,x in d.groupby("half"):
        x = x.copy(); x["p"] = lr.predict_proba(F(x))[:,1]
        fa = 0.07*x.next_ask*(1-x.next_ask); fb = 0.07*x.next_bid*(1-x.next_bid)
        for m in [0.0,0.02,0.04,0.06]:
            b = x.next_ask.notna() & (x.p-x.next_ask-fa>m); se = x.next_bid.notna() & (x.next_bid-x.p-fb>m)
            pb = (x.y-x.next_ask-fa)[b]; ps = (x.next_bid-x.y-fb)[se]
            # favourite-only
            pf = np.concatenate([pb[x.mid[b]>0.5], ps[x.mid[se]<0.5]]); pu = np.concatenate([pb[x.mid[b]<=0.5], ps[x.mid[se]>=0.5]])
            print(f"  {half} m={m}: buy n={len(pb)} {100*pb.mean():+.2f} sell n={len(ps)} {100*ps.mean():+.2f} | fav n={len(pf)} {100*pf.mean():+.2f} dog n={len(pu)} {100*pu.mean():+.2f}")
