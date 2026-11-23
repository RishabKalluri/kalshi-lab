import numpy as np, pandas as pd, sys
from sklearn.ensemble import HistGradientBoostingRegressor
from kalshi_lab.validate import LOCKBOX_START
cut = pd.Timestamp(LOCKBOX_START, tz="UTC") if pd.Timestamp(LOCKBOX_START).tzinfo is None else pd.Timestamp(LOCKBOX_START)
frames=[]
for i,c in enumerate(["BTC","ETH","SOL","XRP","DOGE"]):
    d=pd.read_parquet(f"research/data/KX{c}15M.parquet"); d["coin"]=i; frames.append(d)
d=pd.concat(frames); d=d[d.close<cut].copy()
d=d[(d.h>=60)&(d.h<=600)]
d["z"]=d.D/(d.rv_60m*np.sqrt(d.h)+1e-12)
d["z5"]=d.D/(d.rv_5m*np.sqrt(d.h)+1e-12)
d["ivr"]=d.iv/d.rv_60m; d["ivr4"]=d.iv/d.rv_4h; d["vr"]=d.rv_5m/d.rv_60m; d["vr2"]=d.rv_15m/d.rv_4h
d["hour"]=d.close.dt.hour; d["dow"]=d.close.dt.dayofweek; d["wk"]=(d.dow>=5).astype(int)
d["lc"]=np.log1p(d.n_trades)
d=d.dropna(subset=["ask","bid","z","ivr","ivr4"])
fee=lambda p:0.07*p*(1-p)
d["ey"]=d.y-d.ask-fee(d.ask)
d["en"]=d.bid-d.y-fee(1-d.bid)   # buy NO at 1-bid
d["month"]=d.close.dt.strftime("%Y-%m")
F=["z","z5","ivr","ivr4","vr","vr2","h","hour","wk","coin","lc","mid","age_ask","age_bid","D"]
d["Dn"]=d.D/d.S
F[-1]="Dn"; d["Dn"]=d.D/d.S
months=sorted(d.month.unique()); print(months, len(d))
out=[]
for m in months[3:]:
    tr=d[d.month<m]; te=d[d.month==m]
    if len(te)==0: continue
    for side,col,price in (("y","ey","ask"),("n","en","bid")):
        mdl=HistGradientBoostingRegressor(max_depth=3,max_iter=150,learning_rate=0.05,min_samples_leaf=400,l2_regularization=5.0)
        mdl.fit(tr[F],tr[col])
        te=te.assign(**{"p"+side:mdl.predict(te[F])})
    out.append(te)
r=pd.concat(out)
for thr in (0.01,0.02,0.03,0.05):
    rows=[]
    for side,col in (("y","ey"),("n","en")):
        s=r[r["p"+side]>thr]; rows.append(s.assign(net=s[col],side=side))
    s=pd.concat(rows)
    # one trade per market (first by earliest checkpoint = highest h) 
    s=s.sort_values("h",ascending=False).groupby("ticker").head(1)
    g=s.groupby("month").net.agg(["mean","count"])
    se=s.net.std()/np.sqrt(len(s))
    print(thr, "N",len(s),"mean %.2fc"%(100*s.net.mean()),"se %.2f"%(100*se), "months+",(g["mean"]>0).sum(),"/",len(g))
    print((100*g["mean"]).round(1).to_dict())
    print(s.groupby("coin").net.agg(["mean","count"]).round(3).to_dict())

print("---- realistic fills (next_ask/next_bid within 10s)")
for thr in (0.02,0.03,0.04):
    rows=[]
    s=r[r.py>thr].dropna(subset=["next_ask"]); rows.append(s.assign(net=s.y-s.next_ask-fee(s.next_ask),side="y"))
    s=r[r.pn>thr].dropna(subset=["next_bid"]); rows.append(s.assign(net=s.next_bid-s.y-fee(1-s.next_bid),side="n"))
    s=pd.concat(rows).sort_values("h",ascending=False).groupby("ticker").head(1)
    g=s.groupby("month").net.mean()
    print(thr,"N",len(s),"mean %.2fc"%(100*s.net.mean()),"se %.2f"%(100*s.net.std()/np.sqrt(len(s))),(100*g).round(1).to_dict())
    print(" side",s.groupby("side").net.agg(["mean","count"]).round(3).to_dict(), "h",s.groupby("h").net.agg(["mean","count"]).round(3)["count"].to_dict())
    print(" price band", s.assign(pb=pd.cut(s.mid,[0,.1,.3,.5,.7,.9,1])).groupby("pb",observed=True).net.agg(["mean","count"]).round(3).to_dict())
# permutation-ish importance on last fold
from sklearn.inspection import permutation_importance
tr=d[d.month<months[-1]]; te=d[d.month==months[-1]]
mdl=HistGradientBoostingRegressor(max_depth=3,max_iter=150,learning_rate=0.05,min_samples_leaf=400,l2_regularization=5.0).fit(tr[F],tr.ey)
pi=permutation_importance(mdl,te[F],te.ey,n_repeats=3,random_state=0)
print(dict(zip(F,pi.importances_mean.round(5))))
