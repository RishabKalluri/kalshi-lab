import json, os, sys, time, urllib.request, datetime as dt
from concurrent.futures import ThreadPoolExecutor
OUT='games'
def get(u):
    for i in range(4):
        try:
            return json.load(urllib.request.urlopen(urllib.request.Request(u,headers={'User-Agent':'Mozilla/5.0'}),timeout=30))
        except Exception as e: time.sleep(1+i)
    return None
def game(eid):
    f=f'{OUT}/{eid}.json'
    if os.path.exists(f): return
    d=get(f'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/summary?event={eid}')
    if not d: return
    comp=d['header']['competitions'][0]
    if comp['status']['type']['name']!='STATUS_FINAL': return
    teams={c['homeAway']:c['team']['abbreviation'] for c in comp['competitors']}
    pc=(d.get('pickcenter') or [{}])[0]
    pl=[(p.get('sequenceNumber'),p['period']['number'],p['clock']['displayValue'],p.get('awayScore'),p.get('homeScore'),p.get('wallclock'),p['type'].get('text'),(p.get('strength') or {}).get('abbreviation'),(p.get('team') or {}).get('id'),p.get('scoringPlay')) for p in d.get('plays',[]) if 'period' in p and 'clock' in p]
    json.dump(dict(id=eid,date=comp['date'],season=d['header']['season'],teams=teams,odds=dict(ml_home=(pc.get('homeTeamOdds') or {}).get('moneyLine'),ml_away=(pc.get('awayTeamOdds') or {}).get('moneyLine'),ou=pc.get('overUnder'),spread=pc.get('spread')),plays=pl),open(f,'w'))
def day(ds):
    d=get(f'https://site.api.espn.com/apis/site/v2/sports/hockey/nhl/scoreboard?dates={ds}')
    return [e['id'] for e in (d or {}).get('events',[])]
start=dt.date(2022,10,7); end=dt.date(2026,6,25); days=[]
x=start
while x<=end:
    if not (7<=x.month<=9): days.append(x.strftime('%Y%m%d'))
    x+=dt.timedelta(1)
with ThreadPoolExecutor(5) as ex:
    ids=[i for r in ex.map(day,days) for i in r]
    print('games',len(ids),flush=True)
    list(ex.map(game,ids))
print('done',len(os.listdir(OUT)))
