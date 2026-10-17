"""Does the fade of the previous window's move (z15 = (K-Kp)/(rv_60m*30)) work better when other coins moved the same way?
Fill at h=840 next fill (taker, after fee). Trigger |z15|>1.5, mid .3-.7. Splits: others' mean z15 same sign & >1 (wide) vs not."""
import numpy as np, pandas as pd
fee = lambda p: 0.07*p*(1-p)
coins=["KXBTC15M","KXETH15M","KXSOL15M","KXXRP15M","KXDOGE15M"]
Z={}; F={}
for s in coins:
    d=pd.read_parquet(f"research/data/{s}.parquet"); x=d[d.h==840].sort_values("close").drop_duplicates("close").set_index("close")
    prev = x.index - pd.Timedelta(minutes=15)
    Kp = x.K.reindex(prev).values
    x["z"]=(x.K-Kp)/(x.rv_60m*30); x=x[(x.K/Kp-1).abs()<0.02]
    Z[s]=x.z; F[s]=x
Zdf=pd.DataFrame(Z)
for s in coins:
    x=F[s].copy(); others=Zdf.drop(columns=s)
    x["oz"]=others.mean(axis=1).reindex(x.index); x["on"]=others.notna().sum(axis=1).reindex(x.index)
    x=x[(x.z.abs()>1.5)&x.next_ask.notna()&x.next_bid.notna()&(x.on>=2)&(x.mid.between(.3,.7))]
    med=x.index[len(x)//2]
    print(s,len(x))
    for lab,m in (("wide (oz same sign, |oz|>1)",(np.sign(x.oz)==np.sign(x.z))&(x.oz.abs()>1)),("idio (|oz|<0.5)",x.oz.abs()<.5),("all",x.z==x.z)):
        out=[]
        for nm,g in (("A",x[m&(x.index<med)]),("B",x[m&(x.index>=med)])):
            pnl=np.where(g.z<0,g.y-g.next_ask-fee(g.next_ask),g.next_bid-g.y-fee(1-g.next_bid))
            out.append(f"{nm}: {pnl.mean()*100:+.1f}c n={len(pnl)} se={pnl.std()/max(1,len(pnl))**.5*100:.1f}")
        print("  ",lab,"|"," | ".join(out))
