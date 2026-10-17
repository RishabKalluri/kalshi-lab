import numpy as np, pandas as pd
rows=[]
for coin in ["ETH","SOL","BTC"]:
    d=pd.read_pickle(f"/tmp/who_{coin}.pkl"); d["coin"]=coin; rows.append(d)
d=pd.concat(rows); d=d[(d.az>1.0)&d.mid.between(0.1,0.9)].copy()
up=d.D>0
d["res"]=np.where(up,d.y-d.mid,(1-d.y)-(1-d.mid))  # follow gross edge at mid
for f in ["perp_imb","spot_imb","bigprint","avg_size","lead","n_rate","perp_share"]:
    d[f+"_r"]=d.groupby(["coin","h"])[f].rank(pct=True)-0.5
print("mean res c", 100*d.res.mean(), len(d))

def ols(X,y,g):
    X=np.column_stack([np.ones(len(X)),X]); b=np.linalg.lstsq(X,y,rcond=None)[0]; u=y-X@b
    XtXi=np.linalg.inv(X.T@X); S=np.zeros((X.shape[1],)*2)
    df=pd.DataFrame(X*u[:,None]).groupby(g).sum().to_numpy(); S=df.T@df
    V=XtXi@S@XtXi; return b,b/np.sqrt(np.diag(V))
for coin in ["ETH","SOL","BTC","ALL"]:
    e=d if coin=="ALL" else d[d.coin==coin]
    cols=[c for c in e.columns if c.endswith("_r")]
    b,t=ols(e[cols].to_numpy(),100*e.res.to_numpy(),e.ticker.to_numpy())
    print(coin,dict(zip(["c"]+cols,b.round(2)))); print("  t",dict(zip(["c"]+cols,t.round(1))))
# joint 'forced' cell vs 'informed' cell
d["forced"]=(d.bigprint_r>0.2)&(d.lead_r>0.2)&(d.n_rate_r<0)
d["informed"]=(d.bigprint_r<-0.2)&(d.lead_r<0.2)&(d.n_rate_r>0)
for k in ["forced","informed"]:
    e=d[d[k]]; print(k,len(e),"follow gross c",round(100*e.res.mean(),2),"se",round(100*e.res.std()/np.sqrt(e.ticker.nunique()),2))
