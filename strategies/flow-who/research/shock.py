"""Event study: 30 s shocks in spot, classified by perp flow; later spot return (same direction positive = continuation) in
units of 1h-rv sigma of the horizon. Dev only, non-overlapping events (cooldown 300 s)."""
import sys, numpy as np, pandas as pd
from kalshi_lab.data.flow import load_flow
from kalshi_lab.validate import LOCKBOX_START
cut = LOCKBOX_START.strftime("%Y-%m-%d")
W=30
for coin in ["eth","sol","btc"]:
    fb=load_flow(f"binance_{coin}usdt","2025-12-01",cut,dense=True); fo=load_flow(f"okx_{coin}usdtswap","2025-12-01",cut,dense=True)
    t0=max(fb.t.iloc[0],fo.t.iloc[0]); t1=min(fb.t.iloc[-1],fo.t.iloc[-1])
    fb=fb[(fb.t>=t0)&(fb.t<=t1)].reset_index(drop=True); fo=fo[(fo.t>=t0)&(fo.t<=t1)].reset_index(drop=True)
    n=min(len(fb),len(fo)); fb,fo=fb.iloc[:n],fo.iloc[:n]
    px=fb.px.to_numpy(); lp=np.log(px); r1=np.diff(lp,prepend=lp[0])
    sig=pd.Series(r1**2).rolling(3600).mean().pow(0.5).shift(1).to_numpy()   # per-sec sigma, lagged
    ret=lp-np.roll(lp,W); z=ret/(sig*np.sqrt(W))
    ov=(fo.buy+fo.sell).to_numpy(); ovW=pd.Series(ov).rolling(W).sum().to_numpy()
    base=pd.Series(ovW).rolling(3600*6).median().shift(1).to_numpy()
    vr=ovW/base
    mx=pd.Series(fo.max_trade.fillna(0).to_numpy()).rolling(W).max().to_numpy(); big=mx/np.maximum(ovW,1e-9)
    ob=(fo.buy-fo.sell).to_numpy(); imb=pd.Series(ob).rolling(W).sum().to_numpy()/np.maximum(ovW,1e-9)*np.sign(ret)
    bv=(fb.buy+fb.sell).to_numpy(); bvW=pd.Series(bv).rolling(W).sum().to_numpy()
    perpshare=ovW/np.maximum(ovW+bvW,1e-9)
    # perp price vs spot: perp lead = perp return over W minus spot return
    pret=np.log(fo.px.ffill().to_numpy()); pr=(pret-np.roll(pret,W)); lead=(pr-ret)*np.sign(ret)/(sig*np.sqrt(W))
    idx=np.where((np.abs(z)>3)&(vr>3)&np.isfinite(sig)&np.isfinite(base))[0]
    ev=[];last=-10**9
    for i in idx:
        if i-last>=300 and i+600<n: ev.append(i);last=i
    ev=np.array(ev); s=np.sign(ret[ev])
    d=pd.DataFrame({"t":fb.t.to_numpy()[ev],"z":np.abs(z[ev]),"vr":vr[ev],"big":big[ev],"imb":imb[ev],"share":perpshare[ev],"lead":lead[ev]})
    for H in (60,180,300,600):
        d[f"f{H}"]=s*(lp[ev+H]-lp[ev])/(sig[ev]*np.sqrt(H))
    d["month"]=pd.to_datetime(d.t,unit="s").dt.strftime("%Y-%m")
    print(f"\n{coin}: events {len(d)} (~{len(d)/9:.0f}/month)  mean continuation (sigma units) f60 {d.f60.mean():+.3f} f180 {d.f180.mean():+.3f} f300 {d.f300.mean():+.3f} f600 {d.f600.mean():+.3f}  se~{d.f300.std()/np.sqrt(len(d)):.3f}")
    for f in ["big","imb","share","lead","vr"]:
        d["q"]=pd.qcut(d[f].rank(method="first"),3,labels=False)
        g=d.groupby("q")[["f60","f180","f300"]].mean().round(3)
        print(f, "tercile means f60/f180/f300:", " | ".join(f"{g.loc[i,'f60']:+.2f}/{g.loc[i,'f180']:+.2f}/{g.loc[i,'f300']:+.2f}" for i in range(3)))
    d.to_pickle(f"/tmp/shock_{coin}.pkl")
