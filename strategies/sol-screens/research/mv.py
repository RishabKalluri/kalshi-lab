import pandas as pd, numpy as np
from scipy.stats import norm
d=pd.read_parquet('research/data/KXSOL15M.parquet')
def fee(p): return 0.07*p*(1-p)
d['half']=np.where(d.close<'2026-05-01',0,1)
rows=[]
for h0,h1 in [(840,600),(600,360),(840,360),(480,240),(360,180)]:
    a=d[d.h==h0].set_index('ticker'); b=d[d.h==h1].set_index('ticker')
    j=b.join(a[['mid','D','rv_60m']],rsuffix='0',how='inner').dropna(subset=['mid','mid0'])
    j['dm']=j.mid-j.mid0
    # spot-explained part: model prob change
    sig=j.rv_60m*np.sqrt(h1-40)
    j['pm']=norm.cdf(j.D/sig); 
    sig0=j.rv_60m*np.sqrt(h0-40); j['pm0']=norm.cdf(j.D0/sig0)
    j['res']=j.dm-(j.pm-j.pm0)
    for nm in ('dm','res'):
        j['q']=pd.qcut(j[nm],5,labels=False)
        for q in (0,4):
            for hf in (0,1):
                s=j[(j.q==q)&(j.half==hf)]
                if q==0: # moved down -> buy YES (revert) 
                    t=s.dropna(subset=['next_ask']); pn=t.y-t.next_ask-fee(t.next_ask)
                else:
                    t=s.dropna(subset=['next_bid']); pn=(1-t.y)-(1-t.next_bid)-fee(1-t.next_bid)
                rows.append((h0,h1,nm,q,hf,len(t),round(pn.mean()*100,2)))
print(pd.DataFrame(rows,columns='h0 h1 feat q half n fade_c'.split()).to_string())
