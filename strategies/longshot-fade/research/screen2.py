import sys, numpy as np, collections
sys.path.insert(0,"/srv/kalshi/strategies/longshot-fade/research")
import screen
rows=[r for r in screen.rows if not np.isnan(r[7])]
def run(sel, sign, label, slip=0.01):
    # sign=+1: buy YES after up-move (continuation); -1: buy NO (fade); sel rows have a jump; one check per (market)? count all, cluster by game
    pg=collections.defaultdict(lambda:[0.,0.])
    for s,et,tk,sec,fr,p,y,pp,p0 in sel:
        d=p-pp; side=sign*np.sign(d)
        if side>0: cost=p+slip; w=1.0 if y else 0.0
        else: cost=1-p+slip; w=0.0 if y else 1.0
        pg[et][0]+=w-cost-0.07*cost*(1-cost); pg[et][1]+=1
    a=np.array(list(pg.values()))
    if len(a)<5: print(label,"n/a"); return
    rng=np.random.default_rng(0); idx=rng.integers(0,len(a),(1000,len(a)))
    bs=100*a[idx][:,:,0].sum(1)/a[idx][:,:,1].sum(1)
    print(f"{label:40s} n {int(a[:,1].sum()):6d} games {len(a):4d} net {100*a[:,0].sum()/a[:,1].sum():6.2f}c CI {np.percentile(bs,2.5):6.2f}..{np.percentile(bs,97.5):6.2f}")
for s in ("KXNBAGAME","KXNHLGAME"):
  for thr in (0.05,0.10,0.15):
    sel=[r for r in rows if r[0]==s and abs(r[5]-r[7])>=thr and 0.1<=r[5]<=0.9]
    run(sel,+1,f"{s} jump>={thr} continue"); run(sel,-1,f"{s} jump>={thr} reverse")
# pregame calibration: buy at pre-game price (p0) -- one per market
for s in ("KXNBAGAME","KXNHLGAME"):
  seen={}
  for r in rows:
    if r[0]==s: seen[r[2]]=(r[1],r[8],r[6])
  for lo,hi in ((0.05,.2),(.2,.4),(.4,.6),(.6,.8),(.8,.95)):
    v=[x for x in seen.values() if lo<=x[1]<hi]
    p=np.array([x[1] for x in v]); y=np.array([x[2] for x in v])
    print(s,"pregame",lo,hi,len(v),"price %.3f win %.3f gap %.1fc"%(p.mean(),y.mean(),100*(y.mean()-p.mean())))
