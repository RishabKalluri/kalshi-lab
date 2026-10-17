"""Does the opening price lean on the previous window's outcome (anchoring)? y - fill pnl at h=840 by (y_prev, y_prev2) streak."""
import numpy as np, pandas as pd
fee=lambda p:0.07*p*(1-p)
for s in ["KXXRP15M","KXDOGE15M","KXETH15M"]:
    d=pd.read_parquet(f"research/data/{s}.parquet"); x=d[d.h==840].drop_duplicates("close").set_index("close").sort_index()
    yp=x.y.reindex(x.index-pd.Timedelta(minutes=15)).values; yp2=x.y.reindex(x.index-pd.Timedelta(minutes=30)).values
    x["yp"]=yp; x["yp2"]=yp2; x=x.dropna(subset=["yp","yp2","next_ask","next_bid"]); med=x.index[len(x)//2]
    print(s)
    for lab,m in (("prev up",x.yp==1),("prev down",x.yp==0),("2 up",(x.yp==1)&(x.yp2==1)),("2 down",(x.yp==0)&(x.yp2==0))):
        row=[]
        for nm,mk in (("A",x.index<med),("B",x.index>=med)):
            g=x[m&mk]; 
            row.append(f"{nm}: n={len(g)} y-mid {(g.y-g.mid).mean()*100:+.1f}c buy {((g.y-g.next_ask-fee(g.next_ask)).mean())*100:+.1f} sell {((g.next_bid-g.y-fee(1-g.next_bid)).mean())*100:+.1f}")
        print("  ",lab,"|"," | ".join(row))
