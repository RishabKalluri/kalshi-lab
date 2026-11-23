import pandas as pd, numpy as np, re
st=pd.read_parquet('states.parquet'); st=st[st.season==2026].copy()
me=pd.read_parquet('kal_KXNBAGAME_meta.parquet')
tr=pd.read_parquet('kal_KXNBAGAME_trades.parquet')
KM={'BKN':'BKN','NOP':'NO','GSW':'GS','SAS':'SA','NYK':'NY','WAS':'WSH','UTA':'UTAH','PHX':'PHX'}
def conv(a): return KM.get(a,a)
st['wt3']=pd.to_datetime(st.w_end3,utc=True).astype('datetime64[ns, UTC]').astype('int64'); st['wq4']=pd.to_datetime(st.w_q4,utc=True).astype('datetime64[ns, UTC]').astype('int64')
# kalshi ticker -> away/home codes, date
rows=[]
for tk in me.ticker:
    m=re.match(r'KXNBAGAME-(\d\d)([A-Z]{3})(\d\d)([A-Z]+)-([A-Z]+)$',tk)
    if not m: continue
    yy,mon,dd,pair,team=m.groups()
    dt=pd.to_datetime(f'20{yy}{mon}{dd}',format='%Y%b%d')
    rows.append((tk,dt,pair[:3],pair[3:],team))
k=pd.DataFrame(rows,columns=['ticker','dt','a','h','team']); k['a']=k.a.map(conv); k['h']=k.h.map(conv); k['team']=k.team.map(conv)
st['dt']=pd.to_datetime(st.date)
k=k.merge(st[['game_id','dt','home','away']],left_on=['a','h'],right_on=['away','home'],suffixes=('','_g'))
k=k[(k.dt-k.dt_g).abs()<=pd.Timedelta(days=1)]
print('matched markets',len(k),'of',len(me),'games',k.game_id.nunique())
k=k.merge(me[['ticker','sv']],on='ticker'); k['sv']=k.sv.astype(float)
k=k.merge(st[['game_id','wt3','wq4']],on='game_id')
tr=tr[tr.ticker.isin(k.ticker)].sort_values(['ticker','t'])
res=[]
for tk,g in tr.groupby('ticker'):
    r=k[k.ticker==tk].iloc[0]
    t=g.t.values; p=g.price.values; c=g['count'].values; ts=g.taker.values
    cut=r.wq4-20*10**9
    def last_before(x):
        i=np.searchsorted(t,x,side='right')-1
        return (p[i],t[i]) if i>=0 else (np.nan,np.nan)
    pb,tb=last_before(cut)
    p0,t0=last_before(r.wt3)            # at end of Q3 whistle
    p1,_=last_before(r.wt3+60*10**9)
    lo=np.searchsorted(t,cut-120*10**9); hi=np.searchsorted(t,cut,side='right')
    ww=ts[lo:hi]; pw=p[lo:hi]; cw=c[lo:hi]
    ask=pw[ww=='yes'][-1] if (ww=='yes').any() else np.nan
    bid=pw[ww=='no'][-1] if (ww=='no').any() else np.nan
    vol120=cw.sum()
    lo2=np.searchsorted(t,r.wt3); vbreak=c[lo2:hi].sum()
    # prices in the break window (full)
    res.append(dict(ticker=tk,game_id=r.game_id,team=r.team,a=r.a,h=r.h,sv=r.sv,p_break=pb,age_s=(cut-tb)/1e9 if tb==tb else np.nan,p_endq3=p0,p_q3p60=p1,last_ask=ask,last_bid=bid,vol120=vol120,vol_break=vbreak,ntr_break=hi-lo2))
q=pd.DataFrame(res); q.to_parquet('quotes.parquet'); print(q.describe().T.to_string())
