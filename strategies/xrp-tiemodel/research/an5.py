import pickle, numpy as np, pandas as pd, datetime as dt
D="/srv/kalshi/strategies/xrp-tiemodel/research/data"
df=pd.read_pickle(f"{D}/trades_eval.pkl"); o=pickle.load(open(f"{D}/est.pkl","rb")); est=o['est']; rows=o['rows']
K=np.array([r['K'] for r in rows]); cl=np.array([r['close'] for r in rows])
sg=np.array([min([x for x in o['SS'] if x>=s]) for s in df.s])
x=np.array([est[g][i] for g,i in zip(sg,df.i)])
df['dist']=(x-K[df.i])*1e4; df['px']=K[df.i]
df['mon']=[dt.datetime.fromtimestamp(cl[i],dt.timezone.utc).strftime('%m') for i in df.i]
d=df[(df.s<=30)&(df.s>=3)&(df.dist.abs()<3)]
print(d.groupby(['mon','side']).agg(n=('pnl','size'),pnl=('pnl','mean'),win=('win','mean'),cost=('cost','mean'),px=('px','mean')).unstack())
