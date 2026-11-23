import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor
d=pd.read_parquet("/tmp/wx_snap.parquet")
d=d.dropna(subset=["ask","bid"]).copy()
fee=lambda p:0.07*p*(1-p)
d["tail"]=(d.floor.isna()|d.cap.isna()).astype(int)
d["strike"]=d.floor.fillna(d.cap)
d["mid"]=(d.ask+d.bid)/2; d["spr"]=d.ask-d.bid
d["city"]=d.series.astype("category").cat.codes
d["month"]=d.close.dt.strftime("%Y-%m"); d["moy"]=d.close.dt.month
d["lv"]=np.log1p(d.vol); d["lv1"]=np.log1p(d.vol1h)
d["ey"]=d.y-d.ask-fee(d.ask); d["en"]=d.bid-d.y-fee(1-d.bid)
d=d[(d.ask<=0.99)&(d.bid>=0.01)]
F=["mid","last","spr","h","tail","strike","city","moy","lv","lv1","ntr"]
months=sorted(d.month.unique()); print(months,len(d))
out=[]
for m in months[4:]:
    tr=d[d.month<m]; te=d[d.month==m]
    for side,col in (("y","ey"),("n","en")):
        mdl=HistGradientBoostingRegressor(max_depth=3,max_iter=120,learning_rate=0.05,min_samples_leaf=500,l2_regularization=5.0).fit(tr[F],tr[col])
        te=te.assign(**{"p"+side:mdl.predict(te[F])})
    out.append(te)
r=pd.concat(out)
for thr in (0.01,0.02,0.03,0.05):
    rows=[]
    s=r.dropna(subset=["next_ask"]); s=s[s.py>thr]; rows.append(s.assign(net=s.y-s.next_ask-fee(s.next_ask),side="y"))
    s=r.dropna(subset=["next_bid"]); s=s[s.pn>thr]; rows.append(s.assign(net=s.next_bid-s.y-fee(1-s.next_bid),side="n"))
    s=pd.concat(rows).sort_values("h",ascending=False).groupby("ticker").head(1)
    g=s.groupby("month").net.mean()
    print(thr,len(s),round(100*s.net.mean(),2),round(100*s.net.std()/len(s)**.5,2),(100*g).round(1).tolist(), s.side.value_counts().to_dict())
