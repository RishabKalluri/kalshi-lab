import pandas as pd, numpy as np, datetime as dt
mk=pd.read_parquet('strategies/wx-fcmodel/research/data/mk.parquet'); tr=pd.read_parquet('strategies/wx-fcmodel/research/data/tr.parquet')
mk['d']=mk.ev.str[-7:].map(lambda s: dt.datetime.strptime(s,'%y%b%d'))
tr=tr.merge(mk[['tk','city','d','y']],on='tk')
tr['base']=(tr.d-dt.datetime(1970,1,1)).dt.total_seconds()
tr['hr']=(tr.t-tr.base)/3600
tr['sv']=np.where(tr.side=='yes',1,-1)*tr.q
out=[]
for snap in (8,12,16,20):   # hours after 00Z of event date (event date local day)
    w=tr[(tr.hr<=snap)&(tr.hr>snap-3)]
    g=w.groupby('tk').agg(p=('p','last'),flow=('sv','sum'),vol=('q','sum'),y=('y','first'),city=('city','first'),d=('d','first'),n=('q','size'))
    g=g[(g.p>=0.1)&(g.p<=0.9)&(g.n>=5)]
    g['fi']=g.flow/g.vol
    g['snap']=snap
    out.append(g)
a=pd.concat(out)
a['res']=a.y-a.p
fee=lambda p:0.07*p*(1-p)
for s,g in a.groupby('snap'):
    for lab,m in (('buy-follow fi>0.5',g.fi>0.5),('sell-follow fi<-0.5',g.fi<-0.5)):
        x=g[m]
        r=x.res if 'buy' in lab else -x.res
        r=r-fee(x.p)
        # cluster by date
        dm=r.groupby(x.d).mean()
        print(s,lab,len(x),round(r.mean()*100,2),'se(day)',round(dm.std()/np.sqrt(len(dm))*100,2))
