exec(open('replay.py').read().split("if __name__")[0])
q=pd.read_parquet('quotes.parquet')
S2=pd.read_parquet('snap_quotes.parquet')   # has wall, T, game_id, p via feats
S2['p']=m.predict_proba(feats(S2))[:,1]
S2=S2[S2['T'].isin([300,180,120,60])]
S2['act']=pd.to_datetime(S2.wall,utc=True).astype('datetime64[ns, UTC]').astype('int64')+10*10**9
mk=q.drop_duplicates('ticker')[['ticker','game_id','team','h']]
out=[]
for r in mk.itertuples():
    s=S2[S2.game_id==r.game_id]
    pv=s.p.values if r.team==r.h else 1-s.p.values
    for a,T,pp in zip(s.act.values,s['T'].values,pv): out.append((r.ticker,int(a),int(T),round(float(pp),4)))
o=pd.DataFrame(out,columns=['ticker','act_ns','T','p_yes']); o.to_csv('/srv/kalshi/strategies/nba-q4-state/signals.csv',index=False); print(o.shape,o.head())
