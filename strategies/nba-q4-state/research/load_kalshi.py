import zstandard, json, glob, os, sys, pandas as pd
from datetime import date
LOCK="2026-09-01"
def load(series):
    rows=[];meta=[]
    root=f"/srv/kalshi-data/backfill/kalshi/{series}"
    for d in sorted(os.listdir(root)):
        if d.startswith('_') or d>=LOCK: continue
        for f in glob.glob(f"{root}/{d}/*.jsonl.zst"):
            tk=os.path.basename(f)[:-10]
            dc=zstandard.ZstdDecompressor()
            with open(f,'rb') as fh:
                txt=dc.stream_reader(fh).read().decode()
            for ln in txt.splitlines():
                o=json.loads(ln); m=o['m']
                if m.get('type')=='trade':
                    g=m['msg']; rows.append((tk,o['t'],float(g['yes_price_dollars']),float(g['count_fp']),g['taker_side']))
                elif m.get('event')=='discovered':
                    mk=m['market']; meta.append((tk,mk.get('title'),mk.get('result'),mk.get('settlement_value_dollars'),mk.get('close_time'),mk.get('yes_sub_title'),mk.get('strike_type'),mk.get('floor_strike'),mk.get('cap_strike')))
                elif m.get('event') in ('settled','settlement','result'):
                    pass
    tr=pd.DataFrame(rows,columns=['ticker','t','price','count','taker'])
    me=pd.DataFrame(meta,columns=['ticker','title','result','sv','close','sub','stype','floor','cap']).drop_duplicates('ticker',keep='last')
    return tr,me
if __name__=='__main__':
    s=sys.argv[1]
    tr,me=load(s); tr.to_parquet(f'kal_{s}_trades.parquet'); me.to_parquet(f'kal_{s}_meta.parquet')
    print(s,tr.shape,me.shape); print(me.head(3).T)
