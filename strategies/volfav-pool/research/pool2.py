import pandas as pd, numpy as np
d = pd.read_parquet('/srv/kalshi/strategies/volfav-pool/research/trades2.parquet')
d['month']=d.close.dt.strftime('%Y-%m')
d['pc']=(d.win-d.px-0.07*d.px*(1-d.px))*100
d['we']=d.dow>=5
def summ(s,label):
    mk=s.groupby('ticker').pc.agg(['sum','size']); mu=s.pc.mean()
    se=np.sqrt(((mk['sum']-mk['size']*mu)**2).sum())/mk['size'].sum()
    mm=s.groupby('month').pc.mean()
    print(f'{label:34s} rows {len(s):6d} mk {s.ticker.nunique():5d} {mu:5.2f}c ±{1.96*se:.2f}  pos {int((mm>0).sum())}/{len(mm)}  H1 {s[s.month<"2026-06"].pc.mean():.2f} H2 {s[s.month>="2026-06"].pc.mean():.2f}')
for q in [.6,.7,.8,.9]:
    s=d[d.qthr>q]; summ(s,f'q>{q}'); summ(s[s.px<=.95],f'q>{q} px<=.95'); summ(s[s.we],f'q>{q} weekend'); summ(s[~s.we],f'q>{q} weekday')
    for c,x in s.groupby('coin'): summ(x[x.px<=.95],f'   {c[2:5]} px<=.95')
