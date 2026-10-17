import pandas as pd, numpy as np
for s in ['KXSOL15M','KXETH15M','KXBTC15M']:
    d=pd.read_parquet(f'research/data/{s}.parquet'); d['half']=np.where(d.close<'2026-05-01',0,1)
    d['sig']=d.rv_60m*np.sqrt(d.h)
    d['Dn']=d.D/d.sig; d['mf']=d.move_fut/d.sig
    rows=[]
    for h,g in d.groupby('h'):
        r=[h]
        for hf in (0,1):
            t=g[(g.half==hf)&g.Dn.between(-3,3)].dropna(subset=['Dn','mf'])
            b=np.polyfit(t.Dn,t.mf,1)[0]; r+= [round(b,3), len(t)]
        rows.append(r)
    print(s); print(pd.DataFrame(rows,columns='h b0 n0 b1 n1'.split()).sort_values('h').to_string())
