import pandas as pd, numpy as np
def fee(p): return 0.07*p*(1-p)
for c in ['SOL','ETH','BTC','XRP','DOGE']:
    d=pd.read_parquet(f'research/data/KX{c}15M.parquet'); d=d[d.close<'2026-09-01'].copy()
    d['half']=np.where(d.close<'2026-05-01',0,1)
    a=d.dropna(subset=['next_ask']).copy(); a['ev']=a.y-a.next_ask-fee(a.next_ask); a['pc']=a.next_ask
    b=d.dropna(subset=['next_bid']).copy(); b['pc']=1-b.next_bid; b['ev']=(1-b.y)-b.pc-fee(b.pc)
    for nm,x in [('YES',a),('NO',b)]:
        x['band']=pd.cut(x.pc,[0,.1,.3,.5,.7,.9,1])
        t=x.groupby(['band','half'],observed=True).ev.mean().unstack()*100
        print(c,nm); print(t.round(2).T.to_string())
