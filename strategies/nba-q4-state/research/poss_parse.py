import pandas as pd, numpy as np
R="/srv/kalshi-agents/runs/20261022-1936-4/pbp_raw/"
cols=['game_id','season','season_type','period','team_id','home_team_id','type_text','shooting_play','scoring_play','score_value','end_game_seconds_remaining','sequence_number','game_spread','home_favorite','game_spread_available','home_score','away_score']
out=[]
for y in range(2017,2027):
    p=pd.read_parquet(R+f'pbp_{y}.parquet',columns=cols).sort_values(['game_id','sequence_number'])
    for gid,g in p.groupby('game_id',sort=False):
        if g.season_type.iloc[0] not in (2,3) or g.period.max()<4 or not g.game_spread_available.iloc[0]: continue
        f=g.iloc[0]; em=f.game_spread if f.home_favorite else -f.game_spread; hid=f.home_team_id
        tt=g.type_text.values; tm=g.team_id.values; sc=g.scoring_play.values; sv=g.score_value.values; sec=g.end_game_seconds_remaining.values
        per=g.period.values; hs=g.home_score.values; as_=g.away_score.values; n=len(g)
        off=None; start=None; pts=0; startdiff=0; last_end=sec[0] if n else 2880
        for i in range(n):
            t=tt[i]; team=tm[i]
            if per[i]>4: break
            isft=t.startswith('Free Throw'); isto=('Turnover' in t) or t in ('Traveling','Shot Clock Violation')
            isshot=(not isft) and bool(g.shooting_play.values[i])
            if t=='Defensive Rebound' and team==team:
                # ends previous possession (open one is discarded if it never ended), new possession for rebounder
                if off is not None and off!=team and start is not None:
                    out.append((gid,y,per[i],int(off==hid),start,sec[i],pts,startdiff,em if off==hid else -em)); 
                off=team; start=sec[i]; pts=0
                startdiff=(hs[i]-as_[i]) if team==hid else (as_[i]-hs[i]); last_end=sec[i]; continue
            if (isft or isshot or isto) and team==team:
                if off!=team:
                    if off is not None and start is not None:
                        out.append((gid,y,per[i],int(off==hid),start,sec[i-1] if i>0 else start,pts,startdiff,em if off==hid else -em)); last_end=sec[i-1]
                    off=team; start=last_end; pts=0
                    startdiff=((hs[i]-as_[i]) if team==hid else (as_[i]-hs[i]))-(sv[i] if sc[i] else 0)
                if sc[i]: pts+=int(sv[i])
                ended=False
                if isto: ended=True
                elif isshot and sc[i]:
                    nxt=tt[i+1] if i+1<n else ''
                    ended = not nxt.startswith('Free Throw - 1 of 1')
                elif isft and sc[i]:
                    import re
                    mm=re.search(r'(\d) of (\d)',t); ended = bool(mm and mm.group(1)==mm.group(2))
                if ended:
                    out.append((gid,y,per[i],int(off==hid),start,sec[i],pts,startdiff,em if off==hid else -em)); last_end=sec[i]; off=None

d=pd.DataFrame(out,columns=['game_id','season','period','off_home','start','end','pts','off_diff','off_em'])
d['dur']=d.start-d.end
d.to_parquet('possessions.parquet'); print(d.shape, d.groupby('season').size().head(3)); print(d.pts.value_counts().head(8)); print('ppp',d.pts.mean(),'dur',d.dur.mean(),'per game',len(d)/d.game_id.nunique())
print(d.dur.describe())
