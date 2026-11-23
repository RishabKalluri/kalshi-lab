import pandas as pd, numpy as np, sys
fee=lambda p:0.07*p*(1-p)
def feats(d,slot):
    X=[np.ones(len(d)),np.log(d.rv_5m.clip(lower=1e-7)),np.log(d.rv_15m.clip(lower=1e-7)),np.log(d.rv_60m.clip(lower=1e-7)),np.log(d.rv_4h.clip(lower=1e-7)),np.log(d.h)]
    hr=d.close.dt.hour
    for h in range(1,24): X.append((hr==h).astype(float))
    if slot:
        sl=d.close.dt.minute//15
        for s in (1,2,3): X.append((sl==s).astype(float))
    return np.column_stack(X)
def run(coin):
    d=pd.read_parquet(f'research/data/{coin}.parquet'); d=d[(d.close<'2026-09-01')&d.h.between(60,360)].dropna(subset=['rv_fut','iv','next_ask','next_bid','rv_5m','rv_4h']).copy()
    d=d[(d.rv_fut>0)&(d.iv>0)]
    d['mon']=d.close.dt.strftime('%Y-%m')
    mons=sorted(d.mon.unique())
    out=[]
    for i,m in enumerate(mons):
        if i<3: continue
        tr=d[d.mon.isin(mons[:i])]; te=d[d.mon==m].copy()
        res={}
        for slot in (0,1):
            Xtr=feats(tr,slot); ytr=np.log(tr.rv_fut)
            b=np.linalg.lstsq(Xtr,ytr,rcond=None)[0]
            ftr=np.exp(Xtr@b); fte=np.exp(feats(te,slot)@b)
            rtr=tr.iv/ftr; thr=np.quantile(rtr,0.8)
            te['ratio%d'%slot]=te.iv/fte; te['thr%d'%slot]=thr
            res[slot]=((ytr-Xtr@b)**2).mean()
        te['mse0']=res[0];te['mse1']=res[1]
        out.append(te)
    r=pd.concat(out)
    up=r.mid>=0.5
    px=np.where(up,r.next_ask,1-r.next_bid); won=np.where(up,r.y,1-r.y)
    r['e']=won-px-fee(px)
    r=r[(px>0.5)&(px<0.99)]
    print(coin,len(r),'mse base %.4f slot %.4f'%(r.mse0.mean(),r.mse1.mean()))
    for slot in (0,1):
        s=r[r['ratio%d'%slot]>r['thr%d'%slot]]
        mt=s.groupby('mon').e.mean()
        print('  slot' if slot else '  base','n',len(s),'mean c %.2f'%(s.e.mean()*100),'se %.2f'%(s.e.std()/np.sqrt(len(s))*100),'months+',(mt>0).sum(),'/',len(mt))
    return r


def act(coin):
    r=run(coin)
    s=r[r.ratio1>r.thr1].copy()
    s['q']=pd.qcut(s.n_trades,3,labels=False)
    s['half']=np.where(s.close<'2026-06-01','A','B')
    t=s.groupby(['q','half']).e.agg(['mean','count']).unstack()
    print((t['mean']*100).round(2).assign(nA=t['count']['A'],nB=t['count']['B']).to_string())
