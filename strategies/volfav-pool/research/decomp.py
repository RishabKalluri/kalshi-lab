"""Decompose VolFavorite-style edge on development data, five coins. Walk-forward HAR per coin (fit on prior months only).
Output: research/data-like parquet of per-(market,h) favourite trades with ratio, pnl per contract after fee."""
import sys, numpy as np, pandas as pd
sys.path.insert(0, '/srv/kalshi')
COINS = ['KXBTC15M','KXETH15M','KXSOL15M','KXXRP15M','KXDOGE15M']
H = [360,300,240,180,120,90,60]
def X(d):
    hr = d.close.dt.hour
    return np.column_stack([np.ones(len(d)), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
        *[(hr==k).astype(float) for k in range(1,24)], np.log(d.h)])
out=[]
for s in COINS:
    df = pd.read_parquet(f'/srv/kalshi/research/data/{s}.parquet')
    df = df.dropna(subset=['rv_15m','rv_60m','rv_4h']); df = df[(df.rv_15m>0)&(df.rv_60m>0)&(df.rv_4h>0)].copy()
    df['month'] = df.close.dt.strftime('%Y-%m')
    months = sorted(df.month.unique())
    print(s, df.close.min(), df.close.max(), df.ticker.nunique())
    for m in months[1:]:
        tr = df[(df.month<m)]
        fit = tr[tr.rv_fut>2e-5*tr.S]
        if fit.ticker.nunique()<500: continue
        beta,*_ = np.linalg.lstsq(X(fit), np.log(fit.rv_fut), rcond=None)
        te = df[(df.month==m)&df.h.isin(H)].dropna(subset=['iv']).copy()
        trd = tr[tr.h.isin(H)].dropna(subset=['iv'])
        thr_all = (trd.iv/np.exp(X(trd)@beta))
        te['ratio'] = te.iv/np.exp(X(te)@beta)
        te['qthr'] = np.searchsorted(np.sort(thr_all.values), te.ratio.values)/len(thr_all)  # train percentile of ratio
        te['coin']=s
        out.append(te)
d = pd.concat(out)
fav_yes = d.mid>0.5
d['px'] = np.where(fav_yes, d.next_ask, 1-d.next_bid)   # taker price for fav (prob units)
d['win'] = np.where(fav_yes, d.y, 1-d.y)
d = d.dropna(subset=['px'])
fee = np.ceil(0.07*d.px*(1-d.px)*100)/100
d['pnl'] = d.win - d.px - fee
d['hour']=d.close.dt.hour; d['dow']=d.close.dt.dayofweek
d.to_parquet('/srv/kalshi/strategies/volfav-pool/research/trades.parquet')
print(len(d))
