import pandas as pd, numpy as np
a=pd.read_parquet('/tmp/sol_slots.parquet'); a['v']=a.buy+a.sell; a['sz']=a.v/a.n.replace(0,np.nan); a['imb']=(a.buy-a.sell)/a.v
# trailing 14-day same-slot medians
a=a.sort_index()
for c in ('v','sz'):
    a[c+'_rel']=a[c]/a[c].groupby((a.index%86400)).transform(lambda s:s.shift(1).rolling(14,min_periods=7).median())
d=pd.read_parquet('research/data/KXSOL15M.parquet')
d=d[d.h==840].sort_values('close').copy()
d['Kp']=d.K.shift(1); d['gap']=d.close.diff().dt.total_seconds()
d=d[(d.gap==900)&((d.K/d.Kp-1).abs()<0.02)]
d['C']=(d.close - pd.Timestamp('1970-01-01',tz='UTC')).dt.total_seconds().astype(int)
d['ps']=d.C-1800
d=d.join(a[['v_rel','sz_rel','imb']],on='ps')
fee=lambda p:0.07*p*(1-p)
d['zz']=(d.K/d.Kp-1)/d.rv_60m
thr=d.zz.abs().quantile(0.9)
b=d[(d.zz.abs()>thr)&d.mid.between(.3,.7)].dropna(subset=['v_rel','sz_rel']).copy()
b['ev']=np.where(b.zz<0, b.y-b.next_ask-fee(b.next_ask), (1-b.y)-(1-b.next_bid)-fee(1-b.next_bid))
b=b.dropna(subset=['ev']); b['hf']=np.where(b.close<'2026-05-01','JanApr','MayAug')
b['aligned']=b.imb*np.sign(b.zz)   # >0: taker flow in direction of move
for c in ('v_rel','sz_rel','aligned'):
    b['q']=pd.qcut(b[c],3,labels=['lo','mid','hi'])
    print(c); print(b.groupby(['hf','q'],observed=True).ev.agg(['mean','count','sem']).round(4))
b['vs']=(b.v_rel>2)
print(b.groupby(['hf','vs']).ev.agg(['mean','count']).round(4))
print('=== joint')
b['A']=b.aligned>b.aligned.quantile(2/3); b['S']=b.sz_rel>b.sz_rel.quantile(2/3)
b['mo']=b.close.dt.month
print(b.groupby(['hf','A','S']).ev.agg(['mean','count','sem']).round(4))
x=b[b.A&b.S]; print(x.groupby('mo').ev.agg(['mean','count']).round(3))
x=b[b.A]; print(x.groupby('mo').ev.agg(['mean','count']).round(3))
print('thr', b.aligned.quantile([1/3,2/3,.5]).values)
for t in (0.05,0.1,0.15,0.2,0.3):
    x=b[b.aligned>t]; print(t, len(x), round(x.ev.mean(),4), round(x.ev.sem(),4), 'late', round(x[x.close>='2026-05-01'].ev.mean(),4), len(x[x.close>='2026-05-01']))
