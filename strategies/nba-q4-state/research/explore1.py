import pandas as pd, re
R="/srv/kalshi-agents/runs/20261022-1936-4/pbp_raw/"
p=pd.read_parquet(R+'pbp_2026.parquet',columns=['game_id','game_date','period','clock_display_value','wallclock','away_score','home_score','home_team_abbrev','away_team_abbrev','game_spread','home_team_spread','home_favorite','game_spread_available','season_type','type_text','text','start_game_seconds_remaining','end_game_seconds_remaining','sequence_number'])
print(sorted(set(p.home_team_abbrev)|set(p.away_team_abbrev)))
print(p.season_type.value_counts())
g=p[p.game_id==p.game_id.iloc[5000]]
i=g.index[g.period==3][-1]
print(g.loc[i-3:i+12,['period','clock_display_value','wallclock','away_score','home_score','type_text','text','end_game_seconds_remaining']].to_string())
print(g[['game_spread','home_team_spread','home_favorite']].drop_duplicates())
k=pd.read_parquet('kal_KXNBAGAME_trades.parquet'); print(k.t.min(),k.t.max()); k['tk']=k.ticker
print(k.groupby('ticker').size().describe())
