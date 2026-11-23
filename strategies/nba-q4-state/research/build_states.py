import pandas as pd, numpy as np
R="/srv/kalshi-agents/runs/20261022-1936-4/pbp_raw/"
cols=['game_id','game_date','season','season_type','period','clock_display_value','wallclock','away_score','home_score','home_team_abbrev','away_team_abbrev','game_spread','home_favorite','game_spread_available','type_text','end_game_seconds_remaining','sequence_number','scoring_play','score_value','team_id','home_team_id']
out=[]
for y in range(2017,2027):
    p=pd.read_parquet(R+f'pbp_{y}.parquet',columns=cols)
    p=p.sort_values(['game_id','sequence_number'])
    for gid,g in p.groupby('game_id',sort=False):
        if g.season_type.iloc[0] not in (2,3): continue
        per=g.period.values
        if per.max()<4: continue
        q3=g[g.period==3]; q4=g[g.period==4]
        if len(q3)<20 or len(q4)<20: continue
        a3,h3=q3.away_score.iloc[-1],q3.home_score.iloc[-1]
        q2=g[g.period==2]; a2,h2=q2.away_score.iloc[-1],q2.home_score.iloc[-1]
        q1=g[g.period==1]; a1,h1=q1.away_score.iloc[-1],q1.home_score.iloc[-1]
        fin=g.iloc[-1]
        # final regulation score = last Q4 row
        a4,h4=q4.away_score.iloc[-1],q4.home_score.iloc[-1]
        af,hf=fin.away_score,fin.home_score
        endq3=q3[q3.type_text=='End Period']
        w_end3=endq3.wallclock.iloc[-1] if len(endq3) else q3.wallclock.iloc[-1]
        # first Q4 non-substitution action
        act=q4[~q4.type_text.isin(['Substitution','Ref-Initiated Review (Stands)'])]
        w_q4=act.wallclock.iloc[0] if len(act) else q4.wallclock.iloc[0]
        f=g.iloc[0]
        spr=f.game_spread if f.game_spread_available else np.nan
        hspr=(spr if f.home_favorite else -spr) if spr==spr else np.nan   # expected home margin
        out.append(dict(game_id=gid,season=y,date=str(f.game_date),stype=f.season_type,home=f.home_team_abbrev,away=f.away_team_abbrev,
          exp_margin=hspr,a1=a1,h1=h1,a2=a2,h2=h2,a3=a3,h3=h3,a4=a4,h4=h4,af=af,hf=hf,nper=per.max(),w_end3=w_end3,w_q4=w_q4,
          n_pbp=len(g)))
d=pd.DataFrame(out); d.to_parquet('states.parquet'); print(d.shape); print(d.groupby('season').agg(n=('game_id','size'),spr=('exp_margin',lambda x:x.notna().mean())))
print(d[d.season==2026].head(3).T)
