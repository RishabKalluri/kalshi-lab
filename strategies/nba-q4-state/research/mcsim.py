import pandas as pd, numpy as np, sys
SB=np.array([12,24,48,72,120,180,300,480,10**6]); DB=np.array([-14,-8,-4,-2,0,1,3,5,9,15])  # offense diff bins edges
def sbin(sec): return np.searchsorted(SB,sec,side='right')   # 0..8
def dbin(d): return np.searchsorted(DB,d,side='right')        # 0..10
NS,ND=9,11
class Sim:
    def __init__(self,train_max_season=2024):
        P=pd.read_parquet('possessions.parquet'); P=P[(P.season<=train_max_season)&(P.period==4)&(P.dur>=0)&(P.dur<=40)&(P.start<=720)]
        P=P.assign(b=sbin(P.start.values)*ND+dbin(P.off_diff.values))
        self.dur=[];self.pts=[];self.off=np.zeros(NS*ND,int);self.len=np.zeros(NS*ND,int);pos=0
        for b in range(NS*ND):
            x=P[P.b==b]
            if len(x)<30: x=P[P.b//ND==b//ND]   # fall back to the time bucket
            self.off[b]=pos; self.len[b]=len(x); pos+=len(x); self.dur.append(x.dur.values); self.pts.append(x.pts.values)
        self.dur=np.concatenate(self.dur).astype(np.float32); self.pts=np.concatenate(self.pts).astype(np.int8)
        print('train possessions',len(P),'ppp',self.pts.mean())
    def run(self,sec,diff,pos,em,nsim=400,seed=0,chunk=3000):
        out=np.zeros(len(sec))
        for a in range(0,len(sec),chunk):
            sl=slice(a,a+chunk); out[sl]=self._run(sec[sl],diff[sl],pos[sl],em[sl],nsim,seed+a)
        return out
    def _run(self,sec,diff,pos,em,nsim,seed):
        rng=np.random.default_rng(seed); n=len(sec)
        rem=np.repeat(sec.astype(np.float32)[:,None],nsim,1); d=np.repeat(diff.astype(np.int16)[:,None],nsim,1)
        offh=np.where(pos[:,None]==0,rng.random((n,nsim))<.5,(pos[:,None]==1)&np.ones((n,nsim),bool))   # True = home on offense
        delta=(em/2/100.0)[:,None]*np.ones((n,nsim))   # per-possession expected-points shift for home; away gets -delta
        active=rem>0
        for it in range(200):
            if not active.any(): break
            ii=np.where(active)
            offd=np.where(offh[ii],d[ii],-d[ii]); b=sbin(rem[ii])*ND+dbin(offd)
            j=self.off[b]+(rng.random(len(b))*self.len[b]).astype(int)
            du=np.minimum(self.dur[j],rem[ii]); pt=self.pts[j].astype(np.int16)
            # team-strength shift: home offense scores +delta, away -delta
            sh=np.where(offh[ii],delta[ii],-delta[ii]); u=rng.random(len(b))
            up=(sh>0)&(pt==0)&(u<sh/2); dn=(sh<0)&(pt>=2)&(u<-sh/2)
            pt=np.where(up,2,pt); pt=np.where(dn,0,pt)
            d[ii]=d[ii]+np.where(offh[ii],pt,-pt)
            rem[ii]=rem[ii]-du; offh[ii]=~offh[ii]
            active=rem>0.01
        # ot
        win=(d>0).astype(float); tie=d==0
        pot=np.clip(0.5+0.012*np.repeat(em[:,None],nsim,1),.25,.75)
        win=np.where(tie,pot,win)
        return win.mean(1)
if __name__=='__main__':
    sn=pd.read_parquet('snaps.parquet')
    s=Sim(2024)
    for season in [2025,2026]:
        x=sn[(sn.season==season)].reset_index(drop=True)
        x['p_mc']=s.run(x.sec.values,x['diff'].values,x.pos.values,x.em.values,nsim=400)
        x.to_parquet(f'mc_preds_{season}.parquet'); print(season,'done')
        def LL(y,p): p=np.clip(p,1e-3,1-1e-3); return -(y*np.log(p)+(1-y)*np.log(1-p)).mean()
        for T in sorted(x['T'].unique()): d_=x[x['T']==T]; print(season,T,round(LL(d_.hw,d_.p_mc),4))
