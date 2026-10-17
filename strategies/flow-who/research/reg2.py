import numpy as np, pandas as pd
rows=[]
for coin in ["ETH","SOL","BTC"]:
    d=pd.read_pickle(f"/tmp/who2_{coin}.pkl"); d["coin"]=coin; rows.append(d)
d=pd.concat(rows); d["az"]=d.z.abs(); d=d[(d.az>1.0)&d.mid.between(0.1,0.9)].copy()
d["res"]=np.where(d.z>0,d.y-d.mid,(1-d.y)-(1-d.mid))   # follow edge at mid
F=["perp_imb","spot_imb","bigprint","avg_size","vol_rel","n_rel","perp_share","lead","jump"]
for f in F: d[f+"_r"]=d.groupby(["coin","h"])[f].rank(pct=True)-0.5
def ols(X,y,g):
    X=np.column_stack([np.ones(len(X)),X]); b=np.linalg.lstsq(X,y,rcond=None)[0]; u=y-X@b
    A=np.linalg.inv(X.T@X); s=pd.DataFrame(X*u[:,None]).groupby(g).sum().to_numpy(); V=A@(s.T@s)@A
    return b,b/np.sqrt(np.diag(V))
cols=[f+"_r" for f in F]
for lab,e in [("ALL",d)]+[(c,d[d.coin==c]) for c in ["ETH","SOL","BTC"]]+[("A",d[d.close<pd.Timestamp("2026-05-01",tz="UTC")]),("B",d[d.close>=pd.Timestamp("2026-05-01",tz="UTC")])]:
    b,t=ols(e[cols].to_numpy(),100*e.res.to_numpy(),e.ticker.to_numpy())
    print(lab,len(e)," ".join(f"{c[:-2]}:{x:+.1f}({s:+.1f})" for c,x,s in zip(["c"]+cols,b,t)))
