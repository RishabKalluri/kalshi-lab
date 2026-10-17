import pandas as pd, numpy as np
d = pd.read_parquet('/srv/kalshi/strategies/volfav-pool/research/trades2.parquet')
d['month']=d.close.dt.strftime('%Y-%m'); d['pc']=d.pnl*100
def summ(s,label):
    mk=s.groupby('ticker').pc.agg(['sum','size']); mu=s.pc.mean()
    se=np.sqrt(((mk['sum']-mk['size']*mu)**2).sum())/mk['size'].sum()
    mm=s.groupby('month').pc.mean()
    print(f'{label:34s} rows {len(s):6d} mk {s.ticker.nunique():5d} {mu:5.2f}c ±{1.96*se:.2f}  pos months {int((mm>0).sum())}/{len(mm)}  H1 {s[s.month<"2026-06"].pc.mean():.2f} H2 {s[s.month>="2026-06"].pc.mean():.2f}')
for q in [.5,.6,.7,.8,.85,.9,.95]:
    s=d[d.qthr>q]; summ(s,f'all coins q>{q}')
for q in [.7,.8,.9]:
    for c,x in d[d.qthr>q].groupby('coin'): summ(x,f'  {c} q>{q}')
print('--ex BTC')
for q in [.7,.8,.9]:
    summ(d[(d.qthr>q)&(d.coin!='KXBTC15M')],f'exBTC q>{q}')
print('--price band for q>.8')
s=d[d.qthr>.8]
for lo,hi in [(0,.6),(.6,.7),(.7,.8),(.8,.9),(.9,.95),(.95,1)]:
    summ(s[(s.px>lo)&(s.px<=hi)],f'px {lo}-{hi}')
