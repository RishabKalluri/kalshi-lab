import pandas as pd, numpy as np
R="/srv/kalshi-agents/runs/20261022-1936-4/pbp_raw/"
cols=['game_id','season','season_type','period','wallclock','away_score','home_score','home_team_id','team_id','type_text','scoring_play','score_value','game_spread','home_favorite','game_spread_available','end_game_seconds_remaining','sequence_number','clock_display_value']
TARGETS=[720,480,300,180,120,60]   # game seconds remaining (720 = end of Q3)
out=[]
def poss(tt,team,home_id,scoring,sv,txt):
    # returns +1 if home has the ball next, -1 away, 0 unknown
    if team!=team: return 0
    side = 1 if team==home_id else -1
    if tt in ('Defensive Rebound','Offensive Rebound','Team Rebound'): return side
    if scoring and tt not in ('Free Throw - 1 of 2',) : 
        return -side if 'Free Throw' not in tt or tt.endswith(('2 of 2','1 of 1','3 of 3')) else side
    if 'Turnover' in tt or 'Traveling' in tt or 'Bad Pass' in tt or 'Out of Bounds' in tt: return -side
    return 0
for y in range(2017,2027):
    p=pd.read_parquet(R+f'pbp_{y}.parquet',columns=cols).sort_values(['game_id','sequence_number'])
    for gid,g in p.groupby('game_id',sort=False):
        if g.season_type.iloc[0] not in (2,3): continue
        if g.period.max()<4: continue
        f=g.iloc[0]
        if not f.game_spread_available: continue
        em=f.game_spread if f.home_favorite else -f.game_spread
        sec=g.end_game_seconds_remaining.values; per=g.period.values
        a=g.away_score.values; h=g.home_score.values
        fin=g.iloc[-1]; hw=int(fin.home_score>fin.away_score)
        for T in TARGETS:
            if T==720:
                idx=np.where(per==3)[0]
                if len(idx)==0: continue
                i=idx[-1]
                # use the last Q3 play; state at end of Q3
            else:
                idx=np.where((per==4)&(sec<=T))[0]
                if len(idx)==0: continue
                i=idx[0]
            r=g.iloc[i]
            pos=poss(r.type_text,r.team_id,r.home_team_id,r.scoring_play,r.score_value,'')
            out.append(dict(game_id=gid,season=y,T=T,sec=float(sec[i]) if T!=720 else 720.0,wall=r.wallclock,diff=int(h[i]-a[i]),tot=int(h[i]+a[i]),em=em,pos=pos,hw=hw,period=int(per[i]),
                     ttype=r.type_text))
d=pd.DataFrame(out); d.to_parquet('snaps.parquet'); print(d.shape); print(d.groupby('T').size()); print(d[d['T']==180].pos.value_counts())
