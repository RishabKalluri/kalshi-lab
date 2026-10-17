"""Does recent signed taker flow predict who wins the NEXT fill? For each pre-game taker trade: markout of the taker =
sign*(vwap of trades in (t+60s,t+180s] - p), feature = signed contracts in the previous W seconds (sign: +buy yes)."""
import pandas as pd, numpy as np
R="/srv/kalshi/strategies/pregame-maker/research/"
f=pd.read_parquet(R+"frame.parquet"); t=pd.read_parquet(R+"trades.parquet")
t=t.merge(f[["ticker","start"]],on="ticker").sort_values(["ticker","t"])
t["h"]=(t.start-t.t)/3.6e12
t=t[(t.h>0.15)&(t.h<8)].copy()
t["s"]=np.where(t.side=="yes",1.0,-1.0)
out=[]
for tk,g in t.groupby("ticker"):
    ts=g.t.values/1e9; p=g.p.values*100; n=g.n.values; s=g.s.values
    cs=np.concatenate([[0],np.cumsum(s*n)]); cn=np.concatenate([[0],np.cumsum(n)]); cpn=np.concatenate([[0],np.cumsum(p*n)])
    for W in (30,120,600):
        lo=np.searchsorted(ts,ts-W,side="left"); i=np.arange(len(ts))
        g_=cs[i]-cs[lo]; g_=g_/np.maximum(cn[i]-cn[lo],1)       # flow imbalance in [-1,1] over previous W (excl. self)
        g=g.assign(**{f"f{W}":g_})
    a=np.searchsorted(ts,ts+60,side="right"); b=np.searchsorted(ts,ts+180,side="right")
    vw=(cpn[b]-cpn[a])/np.maximum(cn[b]-cn[a],1e-9); ok=(cn[b]-cn[a])>0
    g=g.assign(mk=np.where(ok,s*(vw-p),np.nan))
    out.append(g[["ticker","n","s","p","mk","f30","f120","f600"]])
d=pd.concat(out).dropna(subset=["mk"])
w=lambda x:(x.mk*x.n).sum()/x.n.sum()
print("overall taker markout c",w(d), "n",len(d))
d["sz"]=pd.cut(d.n,[0,10,50,200,1000,1e9])
print(d.groupby("sz",observed=True).apply(lambda x:pd.Series(dict(n=len(x),mk=w(x)))).round(3))
for W in ("f30","f120","f600"):
    # align flow with taker direction: positive = trade goes WITH recent flow
    d["al"]=d.s*d[W]
    d["ab"]=pd.cut(d.al,[-1.01,-.6,-.2,.2,.6,1.01])
    print(W);print(d.groupby("ab",observed=True).apply(lambda x:pd.Series(dict(n=len(x),ctr=x.n.sum(),mk=w(x)))).round(3))
