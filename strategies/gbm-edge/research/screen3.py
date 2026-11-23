COINS=['SOL','XRP','DOGE']
import numpy as np, pandas as pd, sys
from sklearn.ensemble import HistGradientBoostingRegressor
from kalshi_lab.validate import LOCKBOX_START
cut = pd.Timestamp(LOCKBOX_START, tz="UTC") if pd.Timestamp(LOCKBOX_START).tzinfo is None else pd.Timestamp(LOCKBOX_START)
frames=[]
for i,c in enumerate(COINS):
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


from sklearn.ensemble import HistGradientBoostingClassifier
months=sorted(d.month.unique())
def run(F,thr=(0.02,0.03,0.04),hmax=600):
    out=[]
    for m in months[3:]:
        tr=d[d.month<m]; te=d[d.month==m]
        mdl=HistGradientBoostingClassifier(max_depth=3,max_iter=150,learning_rate=0.05,min_samples_leaf=400,l2_regularization=5.0).fit(tr[F],tr.y)
        out.append(te.assign(p=mdl.predict_proba(te[F])[:,1]))
    r=pd.concat(out); res=[]
    for t in thr:
        rows=[]
        s=r.dropna(subset=["next_ask"]); s=s[s.p-s.next_ask-fee(s.next_ask)>t]; rows.append(s.assign(net=s.y-s.next_ask-fee(s.next_ask),side="y"))
        s=r.dropna(subset=["next_bid"]); s=s[(1-s.p)-(1-s.next_bid)-fee(1-s.next_bid)>t]; rows.append(s.assign(net=s.next_bid-s.y-fee(1-s.next_bid),side="n"))
        s=pd.concat(rows).sort_values("h",ascending=False).groupby("ticker").head(1)
        g=s.groupby("month").net.mean()
        res.append((t,len(s),round(100*s.net.mean(),2),round(100*s.net.std()/len(s)**.5,2),(100*g).round(1).tolist(),s.groupby("coin").net.mean().round(3).to_dict()))
    return res
for name,F in {"C_min":["z5","z","mid","h","coin"],"C2":["z5","z","mid","h","coin","ivr"],"C3":["z5","z","mid","h","coin","wk"]}.items():
    for x in run(F): print(name,x,flush=True)
