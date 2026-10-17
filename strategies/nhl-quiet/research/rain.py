import os, numpy as np, pandas as pd
df = pd.read_parquet(os.environ['KALSHI_AGENT_RUN']+'/work/screen/KXRAIN.parquet')
df['ttc'] = (df.close_ns - df.t) / 3.6e12
df['d'] = pd.to_datetime(df.event.str.split('-').str[1], format='%y%b%d')
def boot(g, n=400):
    a = g.assign(x=g.edge * g.c).groupby('event').agg(x=('x','sum'), c=('c','sum')); a = a[a.c > 0]
    if len(a) < 8: return np.nan, np.nan, np.nan, len(a)
    xs, cs = a.x.values, a.c.values; idx = np.random.default_rng(0).integers(0, len(a), (n, len(a))); m = xs[idx].sum(1) / cs[idx].sum(1)
    return xs.sum()/cs.sum(), *np.percentile(m, [2.5, 97.5]), len(a)
df['tb'] = pd.cut(df.ttc, [-1, 3, 6, 12, 18, 24, 30, 36, 100])
print('hours-to-close buckets: edge of ALL takers; YES takers 10-90c; NO takers 10-90c paid; contracts k')
for k, g in df.groupby('tb', observed=True):
    a = boot(g); y = g[(g.yes) & (g.paid > .1) & (g.paid < .9)]; n = g[(~g.yes) & (g.paid > .1) & (g.paid < .9)]
    by, bn = boot(y), boot(n)
    print(f'{k!s:10} all {a[0]:6.2f} | YES {by[0]:6.2f} [{by[1]:6.2f},{by[2]:6.2f}] {y.c.sum()/1e3:6.0f}k | NO {bn[0]:6.2f} [{bn[1]:6.2f},{bn[2]:6.2f}] {n.c.sum()/1e3:6.0f}k')
# NO taker (paid 10-90c) by month / by day cluster stability, ttc>=6
x = df[(~df.yes) & (df.paid > .1) & (df.paid < .9) & (df.ttc >= 6)]
print('\nNO takers paying 10-90c, ttc>=6h: by month')
for k, g in x.groupby(x.d.dt.strftime('%m')): print(k, boot(g))
print('by price paid'); 
for k, g in x.groupby(pd.cut(x.paid, [.1, .2, .3, .4, .5, .6, .7, .8, .9])): print(k, boot(g), g.c.sum() / 1e3)
# per-day mean to see how many days positive
a = x.assign(w=x.edge * x.c).groupby('d').agg(w=('w','sum'), c=('c','sum')); a['e'] = a.w / a.c
print('days', len(a), 'positive', (a.e > 0).sum(), 'median', a.e.median())
