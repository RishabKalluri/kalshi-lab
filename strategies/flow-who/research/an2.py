import numpy as np, pandas as pd
pd.set_option("display.width",220)
rows=[]
for coin in ["ETH","SOL","BTC"]:
    d=pd.read_pickle(f"/tmp/who2_{coin}.pkl"); d["coin"]=coin; rows.append(d)
d=pd.concat(rows)
d["az"]=d.z.abs()
d["half"]=np.where(d.close<pd.Timestamp("2026-05-01",tz="UTC"),"A","B")
big=d[(d.az>1.5)&d.mid.between(0.1,0.9)]
print("big-move rows",big.groupby("coin").size().to_dict(), "markets/month", (big.groupby("coin").ticker.nunique()/8.5).round(0).to_dict())
for coin in ["ETH","SOL","BTC"]:
    b=big[(big.coin==coin)&big.pnl_follow.notna()]
    print("\n==",coin,len(b),"follow",round(100*b.pnl_follow.mean(),2),"fade",round(100*b.pnl_fade.mean(),2),"gross follow@mid",round(100*b.gross_follow_mid.mean(),2))
    for f in ["perp_imb","spot_imb","imb_rec","bigprint","avg_size","vol_rel","n_rel","perp_share","lead","jump"]:
        q=b.groupby("h")[f].transform(lambda x: pd.qcut(x.rank(method="first"),5,labels=False))
        g=b.assign(q=q).groupby(["q","half"]).agg(n=("pnl_follow","size"),fol=("pnl_follow","mean"))
        print(f"{f:10s} follow c q0..q4 A|B:"," ".join(f"{100*g.loc[(i,'A'),'fol']:+.1f}|{100*g.loc[(i,'B'),'fol']:+.1f}" for i in range(5)))
