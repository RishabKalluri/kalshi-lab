import numpy as np, pandas as pd
from scipy.stats import norm
LOCK = pd.Timestamp("2026-08-20", tz="UTC"); SPLIT = pd.Timestamp("2026-05-01", tz="UTC")
H = [360, 300, 240, 180, 120, 90, 60]
df = pd.read_parquet("research/data/KXSOL15M.parquet")
df = df[df.close < LOCK].dropna(subset=["rv_15m","rv_60m","rv_4h","rv_fut"])
df = df[(df.rv_15m>0)&(df.rv_60m>0)&(df.rv_4h>0)].copy()
df["hour"]=df.close.dt.hour
X = lambda d: np.column_stack([np.ones(len(d)), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h), *[(d.hour==hh).astype(float) for hh in range(1,24)], np.log(d.h)])
tr = df[(df.close<SPLIT)&(df.rv_fut>0.0005)]
beta,*_ = np.linalg.lstsq(X(tr), np.log(tr.rv_fut), rcond=None)
d = df[df.h.isin(H)].dropna(subset=["iv"]).copy()
d = d[(d.mid>0.03)&(d.mid<0.97)&((d.mid-0.5).abs()>0.07)]
d["ratio"] = d.iv/np.exp(X(d)@beta)
fav = d.mid>0.5
d["fwin"]=np.where(fav,d.y,1-d.y); d["fpx"]=np.where(fav,d.next_ask,1-d.next_bid)
d["fpnl"]=d.fwin-d.fpx-0.07*d.fpx*(1-d.fpx)
d=d.dropna(subset=["fpx"])
d["half"]=np.where(d.close<SPLIT,"A","B")
thr = d[d.half=="A"].ratio.quantile(np.linspace(0,1,11))
d["dec"]=pd.cut(d.ratio,thr.values,labels=False,include_lowest=True)
t=d.groupby(["dec","half"]).fpnl.agg(["size","mean"]).unstack(); t[("mean","A")]*=100; t[("mean","B")]*=100
print(t.round(2)); print(thr.round(2).values)
d["zm"]=np.abs(norm.ppf(d.mid))
d["zb"]=pd.cut(d.zm,[0,0.7,1.0,1.414,1.8,9])
top=d[d.dec>=7]
t=top.groupby(["zb","half"],observed=True).fpnl.agg(["size","mean","std"]).unstack()
print(t.round(3))
for (h),x in top.groupby("half"):
    print(h, "by h:", (x.groupby("h").fpnl.mean()*100).round(2).to_dict())
top=top.assign(mon=top.close.dt.month)
print((top.groupby("mon").fpnl.agg(["size","mean"])).round(3))
