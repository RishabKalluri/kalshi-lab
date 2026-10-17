"""Walk-forward (expanding, month by month) GBM on follow-edge at mid using flow features; trade top/bottom predictions at next real fill after fee."""
import numpy as np, pandas as pd
from sklearn.ensemble import HistGradientBoostingRegressor as H
rows=[]
for coin in ["ETH","SOL","BTC"]:
    d=pd.read_pickle(f"/tmp/who2_{coin}.pkl"); d["coin"]=coin; rows.append(d)
d=pd.concat(rows); d["az"]=d.z.abs(); d=d[(d.az>1.0)&d.mid.between(0.1,0.9)].copy()
d["res"]=np.where(d.z>0,d.y-d.mid,(1-d.y)-(1-d.mid))
d["ym"]=d.close.dt.strftime("%Y-%m"); d["ci"]=d.coin.map({"ETH":0,"SOL":1,"BTC":2})
F=["az","perp_imb","spot_imb","imb_rec","bigprint","avg_size","vol_rel","n_rel","perp_share","lead","jump","h","mid","ci","sig"]
d["mid_s"]=np.where(d.z>0,d.mid,1-d.mid)
F=[("mid_s" if f=="mid" else f) for f in F]
months=sorted(d.ym.unique()); res=[]
for m in months[3:]:
    tr=d[d.ym<m]; te=d[d.ym==m].copy()
    mdl=H(max_iter=150,learning_rate=0.05,max_depth=3,min_samples_leaf=200).fit(tr[F],tr.res)
    te["pred"]=mdl.predict(te[F]); res.append(te)
r=pd.concat(res); r=r[r.pnl_follow.notna()]
print("oos corr pred/res",np.corrcoef(r.pred,r.res)[0,1].round(3),"rows",len(r))
for q in [0.5,0.2,0.1,0.05]:
    thr=r.pred.quantile(1-q); e=r[r.pred>=thr]
    e1=e.groupby("ticker").pnl_follow.mean()   # one row per market
    print(f"top {q:.0%}: rows {len(e)} mkts {len(e1)} follow c {100*e.pnl_follow.mean():+.2f}  per-mkt {100*e1.mean():+.2f} se {100*e1.std()/np.sqrt(len(e1)):.2f}  by month:",
          " ".join(f"{100*x:+.1f}" for x in e.groupby("ym").pnl_follow.mean()))
thr=r.pred.quantile(0.05); e=r[r.pred<=thr]; print("bottom 5% fade c",100*e.pnl_fade.mean())
