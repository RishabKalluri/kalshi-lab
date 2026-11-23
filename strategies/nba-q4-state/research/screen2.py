import pandas as pd, numpy as np, joblib
exec(open('model1.py').read().split("tr=sn[")[0].split("sn=pd.read_parquet('snaps.parquet')")[1])
m,lr=joblib.load('model1.joblib')
s=pd.read_parquet('snap_quotes.parquet'); s=s[(s.date<'2026-01-01')].dropna(subset=['mid']).copy()
s['p_hgb']=m.predict_proba(feats(s))[:,1]
c=s[(s['diff'].abs()<=6)&(s['T']<=180)]
print('close games T<=180',len(c),'kalshi',LL(c.hw,c.mid),'hgb',LL(c.hw,c.p_hgb))
for T in [60,120,180]:
    d=c[c['T']==T]; print(T,len(d),'kalshi',round(LL(d.hw,d.mid),4),'hgb',round(LL(d.hw,d.p_hgb),4))
# H6 drift after Q4 scoring plays
R="/srv/kalshi-agents/runs/20261022-1936-4/pbp_raw/"
q=pd.read_parquet('quotes.parquet'); st=pd.read_parquet('states.parquet')[['game_id','date']]
tr=pd.read_parquet('kal_KXNBAGAME_trades.parquet')
h=q[q.team==q.h].drop_duplicates('game_id').merge(st,on='game_id'); h=h[h.date<'2026-01-01']
p=pd.read_parquet(R+'pbp_2026.parquet',columns=['game_id','period','wallclock','scoring_play','score_value','sequence_number','home_score','away_score','end_game_seconds_remaining']).sort_values(['game_id','sequence_number'])
p=p[p.game_id.isin(h.game_id)&(p.period==4)&(p.scoring_play)]
tk=dict(zip(h.game_id,h.ticker)); trg={k:v for k,v in tr[tr.ticker.isin(h.ticker)].groupby('ticker')}
rows=[]
for gid,g in p.groupby('game_id'):
    d=trg[tk[gid]]; t=d.t.values; pr=d.price.values
    w=pd.to_datetime(g.wallclock,utc=True).astype('datetime64[ns, UTC]').astype('int64').values
    px=lambda x:pr[max(np.searchsorted(t,x,side='right')-1,0)]
    for ww,sv,sec,hs,as_ in zip(w,g.score_value.values,g.end_game_seconds_remaining.values,g.home_score.values,g.away_score.values):
        pre=px(ww-5e9); p10=px(ww+10e9); 
        rows.append((gid,sec,hs-as_,pre,p10,px(ww+40e9),px(ww+70e9),px(ww+130e9)))
r=pd.DataFrame(rows,columns=['gid','sec','diff','pre','p10','p40','p70','p130'])
r['jump']=r.p10-r.pre
for lab,mask in [('all',r.jump.abs()>=0),('big|jump|>=3c',r.jump.abs()>=.03),('big>=5c',r.jump.abs()>=.05),('late<300s & >=3c',(r.sec<300)&(r.jump.abs()>=.03)),('late<300s any',(r.sec<300))]:
    x=r[mask&(r.jump!=0)]; sg=np.sign(x.jump)
    for col in ['p40','p70','p130']:
        dr=(x[col]-x.p10)*sg
        print(lab,col,len(x),'cont drift c',round(dr.mean()*100,3),'se',round(dr.std()/np.sqrt(len(x))*100,3))
