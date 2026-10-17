import pandas as pd, numpy as np
d = pd.read_parquet("strategies/wx-bracket-fade/research/snaps.parquet")
d["y"]=(d.result=="yes").astype(float)
d=d[d.ask.notna()&d.bid.notna()&(d.ask_age<120)&(d.bid_age<120)&(d.h>=0)].copy(); d["mid"]=(d.ask+d.bid)/2
fee=lambda p:np.ceil(0.07*p*(1-p)*100-1e-9)/100
x=d[d.mid<.2].copy(); x["pnl_no"]=(1-x.y)-(1-x.bid)-fee(1-x.bid); x["sp"]=x.ask-x.bid
print(x.groupby("series").agg(n=("y","size"),mid=("mid","mean"),freq=("y","mean"),sp=("sp","mean"),pnl_no=("pnl_no","mean")).round(4))
