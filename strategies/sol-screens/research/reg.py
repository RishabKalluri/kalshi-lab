import pandas as pd, numpy as np
o=pd.read_pickle('/tmp/sol_trend.pkl')
grid=pd.date_range(o.index.min(),o.index.max(),freq='15min')
lg=np.log(o.K.reindex(grid)); vol=lg.diff().rolling(288,min_periods=100).std().shift(1)
o['z1']=((lg-lg.shift(1))/vol).reindex(o.index)
def fee(p): return 0.07*p*(1-p)
et=o.index.tz_convert('America/New_York')
o['wk']=np.where(et.dayofweek>=5,'wkend','wkday')
h=et.hour; o['ses']=np.select([(h>=20)|(h<3),(h>=3)&(h<9),(h>=9)&(h<16)],['asia','eu','us'],'late')
# combined reversal pnl: buyYES if z1<-t, buyNO if z1>t
def pn(s,t):
    a=s[s.z1<-t].dropna(subset=['next_ask']); b=s[s.z1>t].dropna(subset=['next_bid'])
    x=pd.concat([a.y-a.next_ask-fee(a.next_ask),(1-b.y)-(1-b.next_bid)-fee(1-b.next_bid)])
    return len(x),round(x.mean()*100,2),round(x.std()/np.sqrt(max(len(x),1))*100,2)
for t in (1.0,1.5):
  for g in ('wk','ses'):
    for k,s in o.groupby(g):
        print(t,g,k,[pn(s[s.half==h],t) for h in (0,1)])
