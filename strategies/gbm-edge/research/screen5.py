import numpy as np, pandas as pd, sys
from sklearn.ensemble import HistGradientBoostingRegressor
from kalshi_lab.validate import LOCKBOX_START
cut = pd.Timestamp(LOCKBOX_START, tz="UTC") if pd.Timestamp(LOCKBOX_START).tzinfo is None else pd.Timestamp(LOCKBOX_START)
frames=[]
for i,c in enumerate(["SOL","XRP","DOGE"]):
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

months=sorted(d.month.unique())
import itertools

F=["z5","z","mid","h"]
out=[]
for m in months[3:]:
    tr=d[d.month<m]; te=d[d.month==m]
    for side,col in (("y","ey"),("n","en")):
        mdl=HistGradientBoostingRegressor(max_depth=3,max_iter=150,learning_rate=0.05,min_samples_leaf=400,l2_regularization=5.0).fit(tr[F],tr[col])
        te=te.assign(**{"p"+side:mdl.predict(te[F])})
    out.append(te)
r=pd.concat(out)
rows=[]
s=r[r.py>0.03]; rows.append(s.assign(net=s.ey,side="y",age=s.age_ask, drift=s.next_ask-s.ask))
s=r[r.pn>0.03]; rows.append(s.assign(net=s.en,side="n",age=s.age_bid, drift=s.bid-s.next_bid))
s=pd.concat(rows).sort_values("h",ascending=False).groupby("ticker").head(1)
s["ab"]=pd.cut(s.age,[-1,5,15,30,60,120,1000])
print("edge at dataset ask/bid, by age of that quote"); print(s.groupby("ab",observed=True).net.agg(["mean","count"]).round(3))
print("edge by side"); print(s.groupby("side").net.agg(["mean","count"]).round(3))
print("mean ask->next_ask drift (cost to wait 10s) for buys", s[s.side=="y"].drift.mean(), "sells",s[s.side=="n"].drift.mean())
print("by coin"); print(s.groupby("coin").net.agg(["mean","count"]).round(3))
print("by mid band"); print(s.groupby(pd.cut(s.mid,[0,.1,.3,.5,.7,.9,1]),observed=True).net.agg(["mean","count"]).round(3))
print("fraction w/ next fill", s.next_ask.notna().mean())
