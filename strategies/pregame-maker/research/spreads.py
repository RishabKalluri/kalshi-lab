import sys, json, random
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0,"/srv/kalshi/src")
from kalshi_lab.recorder.sink import read_lines
R=Path("/srv/kalshi/strategies/pregame-maker/research/")
f=pd.read_parquet(R/"frame.parquet")
random.seed(1)
samp=f.sample(250,random_state=2)
CH=[4320,2880,1440,720,360,180,60,15]
out=[]
for r in samp.itertuples():
    day=pd.to_datetime(r.close,utc=True).date().isoformat()
    p=Path(f"/srv/kalshi-data/backfill/books/{r.series}/{day}/{r.ticker}.jsonl.zst")
    if not p.exists():
        # close date may differ: search
        c=list(Path(f"/srv/kalshi-data/backfill/books/{r.series}").glob(f"*/{r.ticker}.jsonl.zst"))
        if not c: continue
        p=c[0]
    yes,no={},{}
    cps=sorted([(r.start-m*60*10**9,m) for m in CH])
    ci=0; snap={}
    def cur():
        b=max(yes) if yes else None
        a=100-max(no) if no else None
        return b,a,(yes.get(b) if b else 0),(no.get(100-a) if a else 0)
    for ln in read_lines(p):
        d=json.loads(ln); t=d["t"]; m=d["m"]
        while ci<len(cps) and t>=cps[ci][0]:
            snap[cps[ci][1]]=cur(); ci+=1
        if ci>=len(cps): break
        msg=m.get("msg",{})
        if m["type"]=="orderbook_snapshot":
            yes={round(float(a)*100):float(b) for a,b in msg["yes_dollars_fp"]}
            no={round(float(a)*100):float(b) for a,b in msg["no_dollars_fp"]}
        elif m["type"]=="orderbook_delta":
            L=yes if msg["side"]=="yes" else no
            k=round(float(msg["price_dollars"])*100); q=L.get(k,0)+float(msg["delta_fp"])
            if q>1e-9: L[k]=q
            else: L.pop(k,None)
    for mm,(b,a,bq,aq) in snap.items():
        out.append(dict(series=r.series,ticker=r.ticker,mins=mm,bid=b,ask=a,bq=bq,aq=aq))
df=pd.DataFrame(out); df.to_parquet(R/"spreads2.parquet")
df["spread"]=df.ask-df.bid; df["mid"]=(df.ask+df.bid)/2
df=df.dropna()
print(df.groupby(["series","mins"]).agg(n=("spread","size"),spr=("spread","mean"),med=("spread","median"),bq=("bq","median"),aq=("aq","median")))
x=df[(df.mid>=20)&(df.mid<=80)]
print(x.groupby(["series","mins"]).agg(n=("spread","size"),spr=("spread","mean"),med=("spread","median"),bq=("bq","median")))
