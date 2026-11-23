"""Weather snapshot dataset: per (KXHIGH market, hours-before-close) last taker-buy/sell prices, counts, outcome."""
import json, sys, glob, os, io
import numpy as np, pandas as pd
import zstandard as zstd
from multiprocessing import Pool
ROOT="/srv/kalshi-data/backfill/kalshi"
SER=["KXNBAGAME","KXNHLGAME"]
CUT="2026-09-01"
HS=[30,12,6,3,1.5,0.5,-0.5,-1,-1.5,-2,-2.5]
def read(f):
    with open(f,"rb") as fh:
        return [json.loads(l) for l in io.TextIOWrapper(zstd.ZstdDecompressor().stream_reader(fh),encoding="utf8")]
def proc(f):
    L=read(f)
    disc=next((x["m"]["market"] for x in L if x["m"].get("event")=="discovered"),None)
    sett=next((x["m"]["market"] for x in L if x["m"].get("event")=="settled"),None)
    if not disc or not sett or sett.get("result") not in("yes","no"): return []
    close=pd.Timestamp(disc["expected_expiration_time"]).value-171*60*10**9
    tr=[(x["t"],float(x["m"]["msg"]["yes_price_dollars"]),float(x["m"]["msg"]["count_fp"]),x["m"]["msg"]["taker_side"]) for x in L if x["m"].get("type")=="trade"]
    if not tr: return []
    t=np.array([a[0] for a in tr]); p=np.array([a[1] for a in tr]); c=np.array([a[2] for a in tr]); s=np.array([a[3] for a in tr])
    rows=[]
    for h in HS:
        ts=close-int(h*3600*10**9)
        i=np.searchsorted(t,ts,side="right")
        if i==0: continue
        pp,cc,ss=p[:i],c[:i],s[:i]
        ya=np.where(ss=="yes")[0]; na=np.where(ss=="no")[0]
        ask=pp[ya[-1]] if len(ya) else np.nan; bid=pp[na[-1]] if len(na) else np.nan
        # next taker fills within 1h
        j=np.searchsorted(t,ts+3600*10**9,side="right")
        fy=[k for k in range(i,j) if s[k]=="yes"]; fn=[k for k in range(i,j) if s[k]=="no"]
        rows.append(dict(ticker=disc["event_ticker"]+"|"+os.path.basename(f).split(".jsonl")[0],event=disc["event_ticker"],series=disc["event_ticker"].split("-")[0],
            close=pd.Timestamp(disc["close_time"]),h=h,floor=0,cap=0,y=int(sett["result"]=="yes"),
            ask=ask,bid=bid,last=pp[-1],ntr=i,vol=cc.sum(),vol1h=cc[t[:i]>ts-3600*10**9].sum(),
            next_ask=p[fy[0]] if fy else np.nan,next_bid=p[fn[0]] if fn else np.nan))
    return rows
if __name__=="__main__":
    files=[]
    for ser in SER:
        for d in sorted(os.listdir(f"{ROOT}/{ser}")):
            if d>=CUT or d.startswith("_"): continue
            files+=glob.glob(f"{ROOT}/{ser}/{d}/*.jsonl.zst")
    print(len(files),flush=True)
    with Pool(3) as pool: res=pool.map(proc,files,chunksize=50)
    df=pd.DataFrame([r for rr in res for r in rr]); df.to_parquet("/tmp/sp_snap.parquet"); print(df.shape)
