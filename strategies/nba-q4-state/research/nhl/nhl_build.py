import json,glob,numpy as np,pandas as pd,re
def secs(c):
    m=re.match(r'(\d+):(\d+)',c); return int(m.group(1))*60+int(m.group(2)) if m else None
def ml(p): 
    return 100/(p+100) if p>0 else -p/(-p+100)
rows=[]; games=[]
for f in glob.glob('../nhl_raw/games/*.json'):
    g=json.load(open(f)); pl=g['plays']
    if not pl: continue
    o=g['odds']
    if o['ml_home'] is None or o['ml_away'] is None: continue
    ph,pa=ml(o['ml_home']),ml(o['ml_away']); pm=ph/(ph+pa)
    d=pd.DataFrame(pl,columns=['seq','per','clock','a','h','wall','type','str','team','score'])
    d['seq']=d.seq.astype(int); d=d.sort_values('seq'); d['sec']=1200-d.clock.map(secs)
    d=d.dropna(subset=['a','h','sec'])
    if len(d)<50 or d.per.max()<3: continue
    fin=d.iloc[-1]; hw=int(fin.h>fin.a)
    if fin.h==fin.a: continue
    date=g['date'][:10]; 
    d3=d[d.per==3]
    if len(d3)<10: continue
    d3=d3.reset_index(drop=True)
    for T in [1200,600,300,180,120]:
        # first play in P3 with clock remaining <= T (P3 clock counts down); T=1200 -> first play
        x=d3[d3.sec<=T]
        if len(x)==0: continue
        r=x.iloc[0]
        rows.append(dict(game_id=g['id'],date=date,T=T,sec=float(r.sec),diff=int(r.h-r.a),tot=int(r.h+r.a),pm=pm,ou=o['ou'],hw=hw,wall=r.wall,home=g['teams']['home'],away=g['teams']['away'],ptype=r.type,reg=int(d.per.max()==3)))
d=pd.DataFrame(rows); d.to_parquet('nhl_snaps.parquet'); print(d.shape,d.game_id.nunique()); print(d.groupby(d.date.str[:4]).game_id.nunique()); print(d.hw.mean(), d.ptype.value_counts().head(8))
