import pandas as pd, numpy as np
d = pd.read_parquet('/srv/kalshi/strategies/volfav-pool/research/trades.parquet')
d['pc']=d.pnl*100
def t(g):
    return pd.Series(dict(n=len(g), mk=g.ticker.nunique(), c=g.pc.mean(), se=g.pc.std()/np.sqrt(g.ticker.nunique())))
pd.set_option('display.width',200)
d['qb']=pd.cut(d.qthr,[0,.3,.5,.6,.7,.8,.9,1.01])
print(d.groupby(['coin','qb'],observed=True).apply(t).unstack(0)['c'].round(2))
print(d.groupby(['coin','qb'],observed=True).apply(t).unstack(0)['n'])
sel=d[d.qthr>0.6]
d['pb']=pd.cut(d.px,[0,.55,.6,.65,.7,.75,.8,.85,.9,1])
sel=d[d.qthr>0.6]
for col in ['pb','h','hour','dow']:
    print(col); print(sel.groupby([col,'coin'],observed=True).pc.mean().unstack().round(2).assign(ALL=sel.groupby(col,observed=True).pc.mean().round(2), N=sel.groupby(col,observed=True).size()))
