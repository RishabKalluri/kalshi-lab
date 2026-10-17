import pandas as pd, numpy as np, sys
coins=['BTC','ETH','SOL','XRP','DOGE']
F=['rv_5m','rv_15m','rv_60m','rv_4h']
out=[]
for c in coins:
    d=pd.read_parquet(f'/srv/kalshi/research/data/KXET15M.parquet'.replace('KXET',f'KX{c}')).dropna(subset=F+['rv_fut','iv','mid'])
    d=d[(d[F+['rv_fut','iv']]>0).all(axis=1)].copy()
    d['m']=d.close.dt.strftime('%Y-%m')
    for f in F+['rv_fut','iv']: d['l'+f]=np.log(d[f])
    d['pred']=np.nan
    ms=sorted(d.m.unique())
    for m in ms[1:]:
        tr=d[d.m<m]
        if len(tr)<3000: continue
        X=np.c_[np.ones(len(tr)),tr[['l'+f for f in F]].values]
        b=np.linalg.lstsq(X,tr.lrv_fut.values,rcond=None)[0]
        i=d.m==m
        d.loc[i,'pred']=np.c_[np.ones(i.sum()),d.loc[i,['l'+f for f in F]].values]@b
    d=d.dropna(subset=['pred'])
    d['lr']=d.liv-d.pred
    # underdog: side with mid<.5 ; buy at next ask (yes) or 1-next_bid (no)
    yes_dog=d.mid<0.5
    px=np.where(yes_dog,d.next_ask,1-d.next_bid)
    win=np.where(yes_dog,d.y,1-d.y)
    d['px']=px; d['win']=win
    d['pnl']=(win-px-0.07*px*(1-px))*100
    d['coin']=c
    d['wk']=d.close.dt.dayofweek>=5
    out.append(d[['coin','close','m','h','lr','px','win','pnl','wk','mid']])
o=pd.concat(out).dropna(subset=['px'])
o.to_parquet('/srv/kalshi/strategies/volmirror/research/s1.parquet')
o=o[(o.px>0.03)&(o.px<0.5)]
o['q']=o.groupby('coin').lr.rank(pct=True)
o['qb']=pd.cut(o.q,[0,.05,.1,.2,.5,.8,.9,.95,1])
pd.set_option('display.width',200)
print(o.groupby(['qb','coin'],observed=True).pnl.mean().unstack().round(2))
print(o.groupby('qb',observed=True).pnl.agg(['mean','count']).round(2))
