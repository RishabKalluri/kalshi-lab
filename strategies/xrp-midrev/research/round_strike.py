"""Round-number strikes: y - mid at h=720 (and fill pnl) when the strike sits just above/below a round level (pre-stated grids XRP .05 DOGE .005 (+ finer .01/.001))."""
import numpy as np, pandas as pd
fee=lambda p:0.07*p*(1-p)
for s,grids in (("KXXRP15M",(.05,.01)),("KXDOGE15M",(.005,.001))):
    d=pd.read_parquet(f"research/data/{s}.parquet"); d=d[(d.h==720)&d.rv_60m.notna()]
    d=d[d.K.between(d.K.quantile(.02),d.K.quantile(.98))]
    sig=d.rv_60m*30
    med=d.close.quantile(.5)
    for g in grids:
        r=(d.K-np.round(d.K/g)*g)/sig        # K distance to nearest level in 15-min sigmas
        print(s,"grid",g)
        for lo,hi in ((-.5,0),(0,.5),(-1,-.5),(.5,1),(-3,-1),(1,3)):
            m=(r>lo)&(r<=hi)
            row=[]
            for nm,mk in (("A",d.close<med),("B",d.close>=med)):
                x=d[m&mk]
                row.append(f"{nm}: y-mid {((x.y-x.mid).mean()*100):+.1f}c n={len(x)} se={(x.y-x.mid).std()/max(1,len(x))**.5*100:.1f}")
            print(f"  K-R in ({lo},{hi}] sigma | "+" | ".join(row))
