"""Markouts of backtest fills vs book mid (60s/300s later) and touch queue imbalance at fill time. usage: markout.py rundir..."""
import sys, json, bisect
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0,"/srv/kalshi/src")
from kalshi_lab.recorder.sink import read_lines
out=[]
for rd in sys.argv[1:]:
    f=pd.read_csv(rd+"/fills.csv"); f["t"]=pd.to_datetime(f.time,utc=True,format="ISO8601").dt.as_unit("ns").astype("int64")
    mk=pd.read_csv(rd+"/markets.csv")[["ticker","close_time"]]
    f=f.merge(mk,on="ticker"); f["ser"]=f.ticker.str.split("-").str[0]
    for tk,g in f.groupby("ticker"):
        ser=tk.split("-")[0]; day=pd.Timestamp(g.close_time.iloc[0]).date().isoformat()
        p=Path(f"/srv/kalshi-data/backfill/books/{ser}/{day}/{tk}.jsonl.zst")
        if not p.exists(): continue
        ts=sorted(g.t.tolist()); need=[x+t for x in ts for t in (0,60*10**9,300*10**9)]
        need=sorted(set(need)); ni=0; yes,no={},{}; snaps={}
        for ln in read_lines(p):
            d=json.loads(ln); t=d["t"]
            while ni<len(need) and t>need[ni]:
                b=max(yes) if yes else None; a=100-max(no) if no else None
                snaps[need[ni]]=(b,a,yes.get(b,0) if b else 0,no.get(100-a,0) if a else 0); ni+=1
            if ni>=len(need): break
            m=d["m"];msg=m.get("msg",{})
            if m["type"]=="orderbook_snapshot":
                yes={round(float(a)*100):float(b) for a,b in msg["yes_dollars_fp"]}; no={round(float(a)*100):float(b) for a,b in msg["no_dollars_fp"]}
            elif m["type"]=="orderbook_delta":
                L=yes if msg["side"]=="yes" else no; k=round(float(msg["price_dollars"])*100); q=L.get(k,0)+float(msg["delta_fp"])
                if q>1e-9: L[k]=q
                else: L.pop(k,None)
        for r in g.itertuples():
            s0=snaps.get(r.t); s1=snaps.get(r.t+60*10**9); s5=snaps.get(r.t+300*10**9)
            if not s0 or not s0[0] or not s0[1]: continue
            mid=lambda s:(s[0]+s[1])/2 if s and s[0] and s[1] else np.nan
            sgn=1 if r.side=="buy" else -1   # buy yes: gain if mid rises
            out.append(dict(ticker=tk,t=r.t,side=r.side,price=r.price/10,qty=r.qty,mid0=mid(s0),mo60=sgn*(mid(s1)-r.price/10),mo300=sgn*(mid(s5)-r.price/10),
                            bq=s0[2],aq=s0[3],spread=s0[1]-s0[0],run=rd))
df=pd.DataFrame(out); df.to_parquet("/srv/kalshi/strategies/pregame-maker/research/markout.parquet"); 
w=lambda x,c:(x[c]*x.qty).sum()/x.qty.sum() if x[c].notna().any() else np.nan
print("n",len(df),"mo60",w(df,"mo60"),"mo300",w(df,"mo300"))
df["imb"]=np.where(df.side=="buy",np.log((df.bq+1)/(df.aq+1)),np.log((df.aq+1)/(df.bq+1)))   # own-side queue / other side
df["ib"]=pd.qcut(df.imb,5,duplicates="drop")
print(df.groupby("ib",observed=True).apply(lambda x:pd.Series(dict(n=len(x),mo60=w(x,"mo60"),mo300=w(x,"mo300")))).round(3))
df["pb"]=pd.cut(df.price,[0,10,20,40,60,80,90,100])
print(df.groupby("pb",observed=True).apply(lambda x:pd.Series(dict(n=len(x),mo60=w(x,"mo60"),mo300=w(x,"mo300")))).round(3))
fr=pd.read_parquet("/srv/kalshi/strategies/pregame-maker/research/frame.parquet")[["ticker","start","series"]]
df=df.merge(fr,on="ticker",how="left")
df["tts_h"]=(df.start-df.t)/3.6e12
df["tb"]=pd.cut(df.tts_h,[0,0.5,1,2,3,4,6,12,24,48,80])
for s_,g in df.groupby("series"):
    print(s_); print(g.groupby("tb",observed=True).apply(lambda x:pd.Series(dict(n=len(x),ctr=x.qty.sum(),mo60=w(x,"mo60"),mo300=w(x,"mo300")))).round(3))
