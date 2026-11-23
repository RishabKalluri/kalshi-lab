import json,glob,numpy as np
rows=[]
for f in sorted(glob.glob('strategies/*/results.json')):
    s=f.split('/')[1]
    try: runs=json.load(open(f))['runs']
    except Exception: continue
    full=[r for r in runs if r['stage']=='full' and r.get('cards',{}).get('POOLED')]
    lb=[r for r in runs if r['stage']=='lockbox' and not r.get('crashed') and r.get('cards',{}).get('POOLED')]
    if not full or not lb: continue
    F=full[-1]['cards']['POOLED']; L=lb[0]['cards']['POOLED']
    rows.append((s,F['pnl_per_contract_c'],F['ci95_c'],F['markets'],L['pnl_per_contract_c'],L['ci95_c'],L['markets'],full[-1].get('verdict')))
rows.sort(key=lambda r:-r[1])
print('%-24s %7s %16s %6s | %7s %16s %5s'%('slug','full c','CI','n','lb c','CI','n'))
for r in rows: print('%-24s %7.2f %7.2f..%-7.2f %6d | %7.2f %7.2f..%-7.2f %5d  %s'%(r[0],r[1],r[2][0],r[2][1],r[3],r[4],r[5][0],r[5][1],r[6],r[7]))
F=np.array([r[1] for r in rows]);L=np.array([r[4] for r in rows]);n=np.array([r[6] for r in rows])
print('n',len(rows),'mean full %.2f mean lockbox %.2f'%(F.mean(),L.mean()),'lockbox>0',(L>0).sum(),'slope(L on F) %.2f'%np.polyfit(F,L,1)[0], 'corr %.2f'%np.corrcoef(F,L)[0,1])
w=n/n.sum(); print('market-weighted lockbox %.2f'%(w@L))
