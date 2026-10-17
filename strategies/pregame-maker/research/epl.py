import sys, json
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0,"/srv/kalshi/src")
from kalshi_lab.recorder.sink import read_lines
from kalshi_lab.validate import LOCKBOX_START
root=Path("/srv/kalshi-data/backfill/kalshi/KXEPLGAME")
rows=[];tr=[]
for f in sorted(root.glob("*/*.jsonl.zst")):
    if f.parent.name>=LOCKBOX_START.strftime("%Y-%m-%d"): continue
    L=list(read_lines(f))
    if not L: continue
    mk=json.loads(L[0])["m"].get("market",{})
    res=None
    for ln in L:
        d=json.loads(ln);m=d["m"]
        if m.get("event")=="settled": res=m.get("market",{}).get("result") or m.get("result")
        elif m.get("type")=="trade":
            g=m["msg"];tr.append((mk["ticker"],d["t"],float(g["yes_price_dollars"]),float(g["count_fp"]),g["taker_side"]))
    rows.append(dict(ticker=mk["ticker"],event=mk["event_ticker"],exp=mk["expected_expiration_time"],result=res,sub=mk.get("yes_sub_title"),open=mk["open_time"],close=mk["close_time"]))
f=pd.DataFrame(rows);t=pd.DataFrame(tr,columns=["ticker","t","p","n","side"])
f["exp_ns"]=pd.to_datetime(f.exp,utc=True,format="ISO8601").map(lambda x:int(x.timestamp()*1e9))
print(len(f), f.event.nunique(), f.result.value_counts().to_dict())
t=t.merge(f[["ticker","exp_ns","result"]],on="ticker")
t["h"]=(t.exp_ns-t.t)/3.6e12
t["y"]=(t.result=="yes").astype(float)
t["edge"]=np.where(t.side=="yes",t.y-t.p,t.p-t.y)
t["bin"]=pd.cut(t.h,[-1,0,1,2,3,4,6,12,24,48,96])
print(t.groupby("bin",observed=True).apply(lambda x: pd.Series(dict(ctr_per_mkt=x.n.sum()/len(f),trades_per_mkt=len(x)/len(f),edge_c=100*(x.edge*x.n).sum()/x.n.sum()))).round(2))
f.to_parquet("/srv/kalshi/strategies/pregame-maker/research/epl_frame.parquet")
pre=t[(t.h>1)&(t.h<48)].copy()
pre["pb"]=pd.cut(pre.p,[0,.1,.2,.3,.4,.5,.6,.8,1])
e=pre.merge(f[["ticker","event"]],on="ticker")
def agg(x):
    n=x.n.sum(); return pd.Series(dict(ctr=n,edge_c=100*(x.edge*x.n).sum()/n,mkts=x.ticker.nunique()))
print(pre.groupby("side").apply(agg).round(2))
print(pre.groupby("pb",observed=True).apply(agg).round(2))
print(pre.groupby(["side","pb"],observed=True).apply(agg).round(2))
# contract-weighted fair check: mean outcome vs mean price by bucket (all trades)
print(pre.groupby("pb",observed=True).apply(lambda x: pd.Series(dict(p=(x.p*x.n).sum()/x.n.sum(), y=(x.y*x.n).sum()/x.n.sum(), mk=x.ticker.nunique()))).round(3))
