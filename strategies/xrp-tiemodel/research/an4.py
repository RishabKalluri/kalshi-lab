import pickle, numpy as np, pandas as pd
D="/srv/kalshi/strategies/xrp-tiemodel/research/data"
df=pd.read_pickle(f"{D}/trades_eval.pkl"); o=pickle.load(open(f"{D}/est.pkl","rb")); est=o['est']; rows=o['rows']
K=np.array([r['K'] for r in rows]); 
sg=np.array([min([x for x in o['SS'] if x>=s]) for s in df.s])
x=np.array([est[g][i] for g,i in zip(sg,df.i)])
df['dist']=(x-K[df.i])*1e4   # ticks, est - strike
df['near']=pd.cut(df.dist,[-100,-6,-3,-1.5,-0.5,0.5,1.5,3,6,100])
df['spb']=pd.cut(df.s,[0,8,15,30,45])
df['mp']=df.cost  # price paid
g=df.groupby(['spb','near','side']).agg(n=('pnl','size'),pnl=('pnl','mean'),win=('win','mean'),cost=('cost','mean'),pm=('pm','mean'))
pd.set_option('display.width',200); pd.set_option('display.max_rows',200)
print(g[g.n>300])
