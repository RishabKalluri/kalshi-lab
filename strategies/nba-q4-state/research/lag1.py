import pandas as pd, numpy as np
R="/srv/kalshi-agents/runs/20261022-1936-4/pbp_raw/"
q=pd.read_parquet('quotes.parquet'); st=pd.read_parquet('states.parquet')
tr=pd.read_parquet('kal_KXNBAGAME_trades.parquet')
h=q[q.team==q.h].drop_duplicates('game_id').merge(st[['game_id','date']],on='game_id'); h=h[h.date<'2026-01-01']
p=pd.read_parquet(R+'pbp_2026.parquet',columns=['game_id','period','wallclock','scoring_play','score_value','sequence_number']).sort_values(['game_id','sequence_number'])
p=p[p.game_id.isin(h.game_id)&(p.scoring_play)]
tk=dict(zip(h.game_id,h.ticker)); trg={k:v for k,v in tr[tr.ticker.isin(h.ticker)].groupby('ticker')}
lags=np.arange(-30,61,3); acc=np.zeros(len(lags)); n=0
for gid,g in p.groupby('game_id'):
    d=trg[tk[gid]]; t=d.t.values; pr=d.price.values
    w=pd.to_datetime(g.wallclock,utc=True).astype('datetime64[ns, UTC]').astype('int64').values
    def px(x):
        i=np.searchsorted(t,x,side='right')-1; return pr[np.clip(i,0,None)]
    for ww in w:
        acc+=np.array([abs(px(ww+(L+2)*10**9)-px(ww+(L-2)*10**9)) for L in lags]); n+=1
print(n); 
for L,a in zip(lags,acc/n): print(L,round(a*100,3))
