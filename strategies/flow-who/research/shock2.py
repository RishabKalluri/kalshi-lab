"""Event study, memory-light: 30 s spot shocks (|z|>3, perp volume >3x 6h median), classified by perp flow; later spot return
(+ = continuation) in sigma units. Month by month (with 7h warmup). Dev only."""
import numpy as np, pandas as pd
from kalshi_lab.data.flow import load_flow
from kalshi_lab.validate import LOCKBOX_START
cut=pd.Timestamp(LOCKBOX_START).strftime("%Y-%m-%d"); W=30
for coin in ["eth","sol","btc"]:
    evs=[]
    for ym in pd.period_range("2025-12","2026-08",freq="M"):
        s0=ym.start_time; s1=ym.end_time.normalize()+pd.Timedelta(days=1)
        a=(s0-pd.Timedelta(hours=8)).strftime("%Y-%m-%d"); b=min(s1.strftime("%Y-%m-%d"),cut)
        # one extra day at end for forward returns
        b2=min((s1+pd.Timedelta(days=1)).strftime("%Y-%m-%d"),cut)
        fb=load_flow(f"binance_{coin}usdt",a,b2,dense=True); fo=load_flow(f"okx_{coin}usdtswap",a,b2,dense=True)
        if len(fb)<30000 or len(fo)<30000: continue
        t0=int(max(fb.t.iloc[0],fo.t.iloc[0])); t1=int(min(fb.t.iloc[-1],fo.t.iloc[-1]))
        fb=fb[(fb.t>=t0)&(fb.t<=t1)].reset_index(drop=True); fo=fo[(fo.t>=t0)&(fo.t<=t1)].reset_index(drop=True); n=min(len(fb),len(fo)); fb,fo=fb.iloc[:n],fo.iloc[:n]
        lp=np.log(fb.px.to_numpy()); r1=np.diff(lp,prepend=lp[0])
        sig=pd.Series(r1**2).rolling(3600).mean().pow(0.5).shift(1).to_numpy()
        ret=lp-np.roll(lp,W); z=ret/(sig*np.sqrt(W))
        ov=(fo.buy+fo.sell).to_numpy(); ovW=pd.Series(ov).rolling(W).sum().to_numpy(); base=pd.Series(ovW).rolling(3600*6).median().shift(1).to_numpy(); vr=ovW/base
        mx=pd.Series(fo.max_trade.fillna(0).to_numpy()).rolling(W).max().to_numpy(); big=mx/np.maximum(ovW,1e-9)
        imb=pd.Series((fo.buy-fo.sell).to_numpy()).rolling(W).sum().to_numpy()/np.maximum(ovW,1e-9)*np.sign(ret)
        bvW=pd.Series((fb.buy+fb.sell).to_numpy()).rolling(W).sum().to_numpy(); share=ovW/np.maximum(ovW+bvW,1e-9)
        pl=np.log(fo.px.ffill().bfill().to_numpy()); lead=((pl-np.roll(pl,W))-ret)*np.sign(ret)/(sig*np.sqrt(W))
        nW=pd.Series(fo.n.to_numpy()).rolling(W).sum().to_numpy(); avg=ovW/np.maximum(nW,1)
        idx=np.where((np.abs(z)>3)&(vr>3)&np.isfinite(sig)&np.isfinite(base))[0]
        ev=[];last=-10**9
        for i in idx:
            tt=fb.t.iloc[i]
            if tt<s0.timestamp() or tt>=s1.timestamp(): continue
            if i-last>=300 and i+600<n: ev.append(i); last=i
        ev=np.array(ev,dtype=int)
        if not len(ev): continue
        s=np.sign(ret[ev]); d=pd.DataFrame({"t":fb.t.to_numpy()[ev],"s":s,"z":np.abs(z[ev]),"vr":vr[ev],"big":big[ev],"imb":imb[ev],"share":share[ev],"lead":lead[ev],"avg":avg[ev]})
        for H in (60,180,300,600): d[f"f{H}"]=s*(lp[ev+H]-lp[ev])/(sig[ev]*np.sqrt(H))
        evs.append(d)
    d=pd.concat(evs); d["month"]=pd.to_datetime(d.t,unit="s").dt.strftime("%Y-%m")
    print(f"\n{coin}: events {len(d)} (~{len(d)/9:.0f}/month) mean continuation f60 {d.f60.mean():+.3f} f180 {d.f180.mean():+.3f} f300 {d.f300.mean():+.3f} f600 {d.f600.mean():+.3f} se~{d.f300.std()/np.sqrt(len(d)):.3f}")
    for f in ["big","imb","share","lead","avg","vr"]:
        d["q"]=pd.qcut(d[f].rank(method="first"),3,labels=False)
        g=d.groupby("q")[["f60","f180","f300","f600"]].mean()
        print(f"{f:6s} tercile f60/f180/f300/f600:"," | ".join("/".join(f"{g.loc[i,c]:+.2f}" for c in g.columns) for i in range(3)))
    d.to_pickle(f"/tmp/shock2_{coin}.pkl")
