"""Engine-fill EV by favourite price band from walk-forward result dirs (dev months only).
usage: uv run python strategies/sol-zfav-cheap/research/band.py <job-prefix> ...   (e.g. sol-zfav-early-1105-014932)"""
import pandas as pd, numpy as np, glob, sys
def load(prefix):
    rows = []
    for d in sorted(glob.glob(f'results/{prefix}-wf-2026-*')):
        f = pd.read_csv(d + '/fills.csv'); m = pd.read_csv(d + '/markets.csv')
        if f.empty: continue
        g = f.groupby('ticker').apply(lambda x: pd.Series({'qty': x.qty.sum(), 'vw': (x.price * x.qty).sum() / x.qty.sum(), 'side': x.side.iloc[0], 't': x.time.iloc[0]}))
        g = g.join(m.set_index('ticker')[['pnl', 'close_time']]); g['mo'] = d[-7:]; rows.append(g)
    a = pd.concat(rows); a['fav'] = np.where(a.side == 'buy', a.vw, 1000 - a.vw) / 1000
    a['tau'] = (pd.to_datetime(a.close_time) - pd.to_datetime(a.t)).dt.total_seconds(); return a
for p in sys.argv[1:]:
    a = load(p); print(p, len(a), 'ev_w', round(a.pnl.sum() / a.qty.sum() * 100, 2))
    g = a.groupby(pd.cut(a.fav, [0, .9, .93, .95, .97, 1]), observed=True).apply(lambda x: pd.Series({'n': len(x), 'ev_w': x.pnl.sum() / x.qty.sum() * 100, 'se': (x.pnl / x.qty).std() * 100 / len(x) ** .5}))
    print(g.round(2).T)
