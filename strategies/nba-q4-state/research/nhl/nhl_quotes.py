import pandas as pd, numpy as np, re
s=pd.read_parquet('nhl_snaps.parquet'); s=s[s.date>='2025-09-25'].copy()
me=pd.read_parquet('kal_KXNHLGAME_meta.parquet'); tr=pd.read_parquet('kal_KXNHLGAME_trades.parquet')
codes={'ANA','BOS','BUF','CAR','CBJ','CGY','CHI','COL','DAL','DET','EDM','FLA','LA','MIN','MTL','NJ','NSH','NYI','NYR','OTT','PHI','PIT','SEA','SJ','STL','TB','TOR','UTA','VAN','VGK','WPG','WSH'}
rows=[]
for tk,sv in zip(me.ticker,me.sv):
    m=re.match(r'KXNHLGAME-(\d\d)([A-Z]{3})(\d\d)([A-Z]+)-([A-Z]+)$',tk)
    if not m: continue
    yy,mon,dd,pair,team=m.groups()
    for k in (2,3):
        if pair[:k] in codes and pair[k:] in codes: a,h=pair[:k],pair[k:]
    else: pass
    try: a,h
    except NameError: continue
    rows.append((tk,pd.to_datetime(f'20{yy}{mon}{dd}',format='%Y%b%d'),a,h,team,float(sv) if sv is not None else np.nan))
k=pd.DataFrame(rows,columns=['ticker','dt','a','h','team','sv'])
s['dt']=pd.to_datetime(s.date)
x=k.merge(s,left_on=['a','h'],right_on=['away','home'],suffixes=('','_g')); x=x[(x.dt-x.dt_g).abs()<=pd.Timedelta(days=1)&True] if False else x[((x.dt-x.dt_g).abs()<=pd.Timedelta(days=1))]
x=x[x.team==x.h]    # home market only
print('matched snapshot rows',len(x),'games',x.game_id.nunique())
trg={k_:v for k_,v in tr[tr.ticker.isin(x.ticker)].groupby('ticker')}
x['wt']=pd.to_datetime(x.wall,utc=True).astype('datetime64[ns, UTC]').astype('int64')
out=[]
for r in x.itertuples():
    d=trg.get(r.ticker)
    if d is None: out.append([np.nan]*8); continue
    t=d.t.values;pr=d.price.values;c=d['count'].values;ts=d.taker.values
    t0=r.wt+10*10**9; i=np.searchsorted(t,t0,side='right')
    mid=pr[i-1] if i>0 else np.nan; age=(t0-t[i-1])/1e9 if i>0 else np.nan
    j=np.searchsorted(t,t0+60*10**9,side='right'); w=slice(i,j)
    yy=np.where(ts[w]=='yes')[0]; nn=np.where(ts[w]=='no')[0]
    out.append([mid,age,pr[w][yy[0]] if len(yy) else np.nan,(t[w][yy[0]]-t0)/1e9 if len(yy) else np.nan,pr[w][nn[0]] if len(nn) else np.nan,(t[w][nn[0]]-t0)/1e9 if len(nn) else np.nan,c[w].sum(),c[w][yy[0]] if len(yy) else np.nan])
x[['mid','age','ask','ask_t','bid','bid_t','vol60','ask_sz']]=out
x=x.drop(columns=['wt']); x.to_parquet('nhl_snap_quotes.parquet')
print(x.groupby('T')[['mid','ask','bid','vol60','age']].agg(['count','median']).T.to_string())
