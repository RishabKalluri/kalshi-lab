exec(open('replay.py').read().split("if __name__")[0])
def trades(d,thr=.02):
    d=d.copy(); d['ey']=d.p_hgb-d.ask-fee(d.ask); d['en']=(1-d.p_hgb)-(1-d.bid)-fee(1-d.bid)
    ty=(d.ey>=thr)&d.ask.notna(); tn=(d.en>=thr)&d.bid.notna()&~ty
    a=d[ty].copy(); a['side']='YES'; a['px']=a.ask; a['win']=a.hw; a['pm']=a.p_hgb
    b=d[tn].copy(); b['side']='NO'; b['px']=1-b.bid; b['win']=1-b.hw; b['pm']=1-b.p_hgb
    t=pd.concat([a,b]); t['pnl']=t.win-t.px-fee(t.px); return t
for nm,D in [('dev',dev),('test',tst)]:
    t=trades(D[D['T'].isin([300,180,120,60])])
    t['bin']=pd.cut(t.px,[0,.1,.25,.5,.75,.9,1])
    print(nm); print(t.groupby('bin').agg(n=('pnl','size'),px=('px','mean'),model=('pm','mean'),win=('win','mean'),pnl=('pnl','mean')).round(3))
    print(t.groupby('side').pnl.agg(['mean','count']).round(3))
    t['dl']=pd.cut(t['diff'].abs(),[-1,3,6,10,15,100]); print(t.groupby('dl').agg(n=('pnl','size'),pnl=('pnl','mean'),win=('win','mean'),px=('px','mean')).round(3))
