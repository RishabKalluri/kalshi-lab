import numpy as np, pandas as pd
from kalshi_lab.data.flow import load_flow
days=pd.date_range('2026-01-05','2026-08-18',freq='4D')
res=[]
for d in days:
    a=d.strftime('%Y-%m-%d'); b=(d+pd.Timedelta(days=1)).strftime('%Y-%m-%d')
    try:
        p=load_flow('okx_solusdtswap',a,b); s=load_flow('binance_solusdt',a,b)
    except Exception: continue
    if len(p)<1000 or len(s)<1000: continue
    t0=min(p.t.min(),s.t.min()); idx=np.arange(t0,t0+86400)
    P=p.drop_duplicates('t').set_index('t').px.reindex(idx).ffill(); S=s.drop_duplicates('t').set_index('t').px.reindex(idx).ffill()
    dev=np.log(P/S); dev=dev-dev.rolling(900,min_periods=300).mean()
    for H in (10,30,120,300):
        fut=np.log(S.shift(-H)/S)
        # signed standardized
        x=dev.iloc[1000::5]; y=fut.iloc[1000::5]
        m=x.notna()&y.notna()
        res.append((a,H,np.corrcoef(x[m],y[m])[0,1],x[m].std()*1e4,y[m].std()*1e4, np.polyfit(x[m],y[m],1)[0]))
r=pd.DataFrame(res,columns=['d','H','corr','devbp','futbp','beta'])
print(r.groupby('H')[['corr','devbp','futbp','beta']].mean())
r['half']=r.d<'2026-05-01'; print(r.groupby(['H','half'])['corr'].mean())
