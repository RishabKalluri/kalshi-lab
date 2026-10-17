import pandas as pd, numpy as np
d=pd.read_parquet('research/data/KXSOL15M.parquet')
def fee(p): return 0.07*p*(1-p)
o=d[d.h==840].sort_values('close').drop_duplicates('ticker').copy()
o['open']=o.close-pd.Timedelta(minutes=15); o=o.set_index('open')
o['b']=(o.basis/o.K*1e4).clip(-40,40)
print(o.b.describe())
o['bdev']=o.b-o.b.rolling(96,min_periods=48).median().shift(1)
o['bdev_s']=o.bdev/o.bdev.rolling(96*3,min_periods=100).std().shift(1)
o['half']=np.where(o.index<'2026-05-01',0,1)
o['Dn']=o.D/(o.rv_60m*np.sqrt(840-40))
print(o[['bdev_s','Dn','y']].corr())

x=o.dropna(subset=['bdev_s','Dn','y'])

x['q']=pd.qcut(x.bdev_s,10,labels=False)
rows=[]
for q,s in x.groupby('q'):
    for hf in (0,1):
        t=s[s.half==hf]; a=t.dropna(subset=['next_ask']); b=t.dropna(subset=['next_bid'])
        rows.append((q,hf,len(t),round(t.y.mean(),3),round(t.mid.mean(),3),round((a.y-a.next_ask-fee(a.next_ask)).mean()*100,2),round(((1-b.y)-(1-b.next_bid)-fee(1-b.next_bid)).mean()*100,2)))
print(pd.DataFrame(rows,columns='q half n y mid buyYES buyNO'.split()).to_string())
