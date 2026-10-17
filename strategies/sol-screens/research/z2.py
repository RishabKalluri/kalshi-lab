import pandas as pd, numpy as np
o=pd.read_pickle('/tmp/sol_trend.pkl')
grid=pd.date_range(o.index.min(),o.index.max(),freq='15min')
lg=np.log(o.K.reindex(grid)); vol=lg.diff().rolling(288,min_periods=100).std().shift(1)
o['z1']=((lg-lg.shift(1))/vol).reindex(o.index)
o['z1b']=((lg.shift(1)-lg.shift(2))/vol).reindex(o.index)  # the window before last
def fee(p): return 0.07*p*(1-p)
def rep(name,s):
    out=[]
    for hf in (0,1):
        t=s[s.half==hf]
        a=t.dropna(subset=['next_ask']); b=t.dropna(subset=['next_bid'])
        out.append((len(t), round(t.y.mean(),3), round((a.y-a.next_ask-fee(a.next_ask)).mean()*100,2), round(((1-b.y)-(1-b.next_bid)-fee(1-b.next_bid)).mean()*100,2)))
    print(name,out)
rep('z2<-1.75 & |z1|<1',o[(o.z2<-1.75)&(o.z1.abs()<1)])
rep('z2<-1.75 & z1<-1',o[(o.z2<-1.75)&(o.z1<-1)])
rep('z2>1.75 & |z1|<1',o[(o.z2>1.75)&(o.z1.abs()<1)])
rep('z1b<-1.5 & |z1|<.7',o[(o.z1b<-1.5)&(o.z1.abs()<.7)])
rep('z1b>1.5 & |z1|<.7',o[(o.z1b>1.5)&(o.z1.abs()<.7)])
rep('z1<-1.5',o[o.z1<-1.5]); rep('z1>1.5',o[o.z1>1.5])
