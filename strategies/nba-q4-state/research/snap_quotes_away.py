import pandas as pd, numpy as np, sys
D=int(sys.argv[1]) if len(sys.argv)>1 else 10
sn=pd.read_parquet('snaps.parquet'); q=pd.read_parquet('quotes.parquet'); st=pd.read_parquet('states.parquet')[['game_id','date']]
tr=pd.read_parquet('kal_KXNBAGAME_trades.parquet')
h=q[q.team==q.a].drop_duplicates('game_id')[['game_id','ticker','sv']]
s=sn[sn.season==2026].merge(h,on='game_id').merge(st,on='game_id')
trg={k:v for k,v in tr[tr.ticker.isin(h.ticker)].groupby('ticker')}
s['wt']=pd.to_datetime(s.wall,utc=True).astype('datetime64[ns, UTC]').astype('int64')
rows=[]
for r in s.itertuples():
    d=trg[r.ticker]; t=d.t.values; pr=d.price.values; c=d['count'].values; ts=d.taker.values
    t0=r.wt+D*10**9
    i=np.searchsorted(t,t0,side='right')
    mid=pr[i-1] if i>0 else np.nan; age=(t0-t[i-1])/1e9 if i>0 else np.nan
    j=np.searchsorted(t,t0+60*10**9,side='right')
    w=slice(i,j)
    yy=np.where(ts[w]=='yes')[0]; nn=np.where(ts[w]=='no')[0]
    ask=pr[w][yy[0]] if len(yy) else np.nan; ask_t=(t[w][yy[0]]-t0)/1e9 if len(yy) else np.nan
    bid=pr[w][nn[0]] if len(nn) else np.nan; bid_t=(t[w][nn[0]]-t0)/1e9 if len(nn) else np.nan
    # depth proxies: contracts traded on that side in the window up to the next 5 s
    ask_sz=c[w][yy[0]] if len(yy) else np.nan; bid_sz=c[w][nn[0]] if len(nn) else np.nan
    w5=slice(i,np.searchsorted(t,t0+5*10**9,side='right')); y5=ts[w5]=='yes'; n5=ts[w5]=='no'
    ask5=pr[w5][y5].max() if y5.any() else np.nan; bid5=pr[w5][n5].min() if n5.any() else np.nan
    w15=slice(i,np.searchsorted(t,t0+15*10**9,side='right')); y15=ts[w15]=='yes'; n15=ts[w15]=='no'
    ask15=pr[w15][y15].max() if y15.any() else np.nan; bid15=pr[w15][n15].min() if n15.any() else np.nan
    rows.append((mid,age,ask,ask_t,bid,bid_t,c[w].sum(),ask_sz,bid_sz,ask5,bid5,ask15,bid15))
s[['mid','age','ask','ask_t','bid','bid_t','vol60','ask_sz','bid_sz','ask5','bid5','ask15','bid15']]=rows
a_ask,a_bid=s.ask.copy(),s.bid.copy()
s['mid']=1-s.mid; s['ask']=1-a_bid; s['bid']=1-a_ask; s['ask_t'],s['bid_t']=s.bid_t.copy(),s.ask_t.copy(); s['ask_sz'],s['bid_sz']=s.bid_sz.copy(),s.ask_sz.copy()
s.drop(columns=['wt']).to_parquet('snap_quotes_away.parquet'); print(s[['ask_sz','bid_sz']].describe())
