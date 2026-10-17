import pandas as pd, numpy as np
rows=[]
for c in ['BTC','ETH','SOL','XRP','DOGE']:
    d=pd.read_parquet(f'research/data/KX{c}15M.parquet'); d['coin']=c; rows.append(d)
D=pd.concat(rows)
D=D[D.mid>0].copy()
D['mon']=D.close.dt.strftime('%Y-%m'); D['half']=np.where(D.mon<'2026-05','A','B')
# H3 flips: sign changes of mid-0.5 over horizons > h within market
D=D.sort_values(['coin','ticker','h'],ascending=[True,True,False])
D['s']=np.sign(D.mid-.5)
D['chg']=(D.s!=D.groupby(['coin','ticker']).s.shift())&D.groupby(['coin','ticker']).s.shift().notna()
D['flips']=D.groupby(['coin','ticker']).chg.cumsum()
# H2 previous window surprise: prev market (close-15m) mid at h=60 vs y
last=D[D.h==60][['coin','close','mid','y']].copy()
last['close']=last.close+pd.Timedelta(minutes=15)
last['surp']=last.y-last.mid   # >0: YES surprised
last=last.rename(columns={'y':'py','mid':'pmid'})
D=D.merge(last,on=['coin','close'],how='left')
fy=D.mid>=.5
p=np.where(fy,D.next_ask,1-D.next_bid); win=np.where(fy,D.y,1-D.y)
D['p']=p; D['net']=win-p-0.07*p*(1-p)
X=D[(D.h>=240)&(D.h<=600)&(D.p>.75)&(D.p<.97)].copy()
print('H3 flips (fav net c)'); print(X.groupby(['half',X.flips.clip(upper=3)]).net.agg(['mean','sem','count']).mul([100,100,1]))
X['sa']=np.where(fy[X.index] if False else (X.mid>=.5),X.surp,-X.surp)  # surprise in direction of current favourite
X['sq']=pd.cut(X.sa,[-1,-.6,-.2,.2,.6,1])
print('H2 prev surprise in fav direction'); print(X.groupby(['half','sq'],observed=True).net.agg(['mean','sem','count']).mul([100,100,1]))
print('H3b underdog after flips')
uy=D.mid<.5
q=np.where(uy,D.next_ask,1-D.next_bid); uw=np.where(uy,D.y,1-D.y)
D['q']=q; D['unet']=uw-q-0.07*q*(1-q)
U=D[(D.h>=240)&(D.h<=600)&(D.q>.05)&(D.q<.4)]
print(U.groupby(['half',U.flips.clip(upper=3)]).unet.agg(['mean','sem','count']).mul([100,100,1]))
U3=U[U.flips>=2].copy(); U3['mon']=U3.close.dt.strftime('%Y-%m')
print(U3.groupby('mon').unet.agg(['mean','count']))
print(U3.groupby('coin').unet.agg(['mean','sem','count']))
