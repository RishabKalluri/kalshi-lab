import sys, numpy as np, pandas as pd
for coin in ["ETH","SOL","BTC"]:
    d = pd.read_pickle(f"/tmp/who_{coin}.pkl")
    big = d[(d.az > 1.0) & d.pnl_follow.notna() & d.pnl_fade.notna() & d.mid.between(0.1, 0.9)]
    print("\n==", coin, len(big), "follow", round(100*big.pnl_follow.mean(),2), "fade", round(100*big.pnl_fade.mean(),2))
    for f in ["perp_imb","spot_imb","bigprint","avg_size","lead","n_rate"]:
        q = big.groupby("h")[f].transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
        g = big.assign(q=q).groupby(["q","half"]).agg(n=("pnl_follow","size"), fol=("pnl_follow", lambda x: 100*x.mean()), fad=("pnl_fade", lambda x: 100*x.mean()))
        print(f, "  q0..q4 follow A|B:", " ".join(f"{g.loc[(i,'A'),'fol']:+.1f}|{g.loc[(i,'B'),'fol']:+.1f}" for i in range(5)),
              "  fade:", " ".join(f"{g.loc[(i,'A'),'fad']:+.1f}|{g.loc[(i,'B'),'fad']:+.1f}" for i in range(5)))
