import zstandard,json,glob,os,sys
import pandas as pd
LOCK='2026-09-01'
rows=[];trs=[]
for d in sorted(glob.glob('/srv/kalshi-data/backfill/kalshi/KXRAIN/*')):
    if os.path.basename(d)>=LOCK: continue
    for f in glob.glob(d+'/*.zst'):
        tk=os.path.basename(f).split('.')[0]
        info={'ticker':tk}
        for line in zstandard.ZstdDecompressor().stream_reader(open(f,'rb')).read().decode().splitlines():
            r=json.loads(line);m=r['m']
            if 'event' in m:
                mk=m['market'];info.setdefault('events',[]).append((m['event'],r['t'],mk.get('status'),mk.get('result')))
                info['close']=mk.get('close_time');info['result']=mk.get('result');info['exp']=mk.get('expected_expiration_time');info['settle_ts']=mk.get('settlement_ts'); info['status']=mk.get('status'); info['rules']=mk.get('rules_primary')
            elif m.get('type')=='trade':
                g=m['msg'];trs.append((tk,r['t'],float(g['yes_price_dollars']),float(g['count_fp']),g['taker_side']))
        rows.append(info)
M=pd.DataFrame(rows);T=pd.DataFrame(trs,columns=['ticker','t','p','n','side'])
M.to_pickle('/tmp/rain_M.pkl');T.to_pickle('/tmp/rain_T.pkl')
print(len(M),len(T))
