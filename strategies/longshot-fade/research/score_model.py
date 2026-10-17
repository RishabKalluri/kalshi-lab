import pickle, numpy as np, collections
from sklearn.linear_model import LogisticRegression
rows = pickle.load(open("/tmp/lf_scores.pkl","rb"))
for s in ("KXNBAGAME","KXNHLGAME"):
    R=[r for r in rows if r[0]==s and 0.03<=r[6]<=0.97]
    ets=sorted({r[1] for r in R}, key=lambda e: min(x[9] for x in R if x[1]==e)) if False else None
    ck=np.array([r[9] for r in R]); cut=np.quantile(ck,0.6)
    tr=[r for r in R if r[9]<cut]; te=[r for r in R if r[9]>=cut]
    def X(rs):
        p=np.array([r[6] for r in rs]); lead=np.array([r[4] for r in rs],float); tl=np.array([r[5] for r in rs],float)
        sc=2.5 if s=="KXNBAGAME" else 1.0
        z=lead/np.sqrt(tl+60)*(1 if s=="KXNBAGAME" else 30)
        return np.c_[np.log(p/(1-p)), z], np.array([r[7] for r in rs])
    Xt,yt=X(tr); Xe,ye=X(te)
    m=LogisticRegression(C=100).fit(Xt,yt); print(s,"coef logit(p), z:",m.coef_[0], "n",len(tr),len(te))
    pe=m.predict_proba(Xe)[:,1]; pm=Xe[:,0]; pm=1/(1+np.exp(-pm))
    ll=lambda q: -np.mean(ye*np.log(q)+(1-ye)*np.log(1-q))
    print("  test logloss market %.4f model %.4f"%(ll(pm),ll(pe)))
    # trade: buy YES if model-p > thr, NO if p-model > thr; net of 1c slip+fee, cluster by game
    for thr in (0.03,0.05,0.08):
        pg=collections.defaultdict(lambda:[0.,0.])
        for r,q,p in zip(te,pe,pm):
            if q-p>thr: cost=p+0.01; w=float(r[7])
            elif p-q>thr: cost=1-p+0.01; w=float(not r[7])
            else: continue
            pg[r[1]][0]+=w-cost-0.07*cost*(1-cost); pg[r[1]][1]+=1
        a=np.array(list(pg.values()))
        if len(a)<5: print(thr,"n/a"); continue
        rng=np.random.default_rng(0); idx=rng.integers(0,len(a),(1000,len(a)))
        bs=100*a[idx][:,:,0].sum(1)/a[idx][:,:,1].sum(1)
        print(f"  thr {thr} n {int(a[:,1].sum())} games {len(a)} net {100*a[:,0].sum()/a[:,1].sum():.2f}c CI {np.percentile(bs,2.5):.2f}..{np.percentile(bs,97.5):.2f}")
