import pandas as pd,numpy as np,re
exec(open('strategies/rain-obs/research/screen1.py').read().split("M=pd.read_pickle")[0])
M=pd.read_pickle('/tmp/rain_M2.pkl');T=pd.read_pickle('/tmp/rain_T.pkl')
O=M.set_index('ticker')
T=T.join(O[['fr2','yes','city','close_ns']],on='ticker',how='inner')
T['h']=(T.close_ns-T.t)/3.6e12
fee=lambda p:np.ceil(0.07*p*(1-p)*100)/100
a=T[(T.side=='no')&(T.h<=6)&(T.h>=.5)&(T.p>=.1)&(T.p<=.9)].sort_values('t').groupby('ticker').head(1).copy()
a['tm']=pd.to_datetime(a.t)
a['seen']=(a.fr2.notna())&(a.fr2+pd.Timedelta(minutes=10)<=a.tm)
a=a[~a.seen]
def feat(r):
    o=obs[r.city];x=o[o.valid<=r.tm-pd.Timedelta(minutes=10)].tail(1)
    m=x.metar.iloc[0] if len(x) else ''
    sky=re.findall(r'\b(CLR|SKC|FEW|SCT|BKN|OVC|VV)\d*',m)
    top={'CLR':0,'SKC':0,'FEW':1,'SCT':2,'BKN':3,'OVC':4,'VV':4}
    s=max([top[k] for k in sky]) if sky else -1
    wx=bool(re.search(r'\s[-+]?(VC)?(RA|TS|DZ|SH|UP|FG|BR)',m.split('RMK')[0]))
    ts=bool(re.search(r'TS',m.split('RMK')[0]))
    mm=re.search(r' (M?\d\d)/(M?\d\d) ',m)
    dd=np.nan
    if mm:
        f=lambda z:-int(z[1:]) if z[0]=='M' else int(z); dd=f(mm.group(1))-f(mm.group(2))
    return pd.Series({'sky':s,'wx':wx,'ts':ts,'dd':dd})
a=a.join(a.apply(feat,axis=1))
a['pnl']=(1-a.yes)-(1-a.p)-fee(1-a.p)
a.to_pickle('/tmp/rain_a.pkl')
for k in ('sky','wx','ts'):
    print(a.groupby(k).agg(n=('yes','size'),yes=('yes','mean'),p=('p','mean'),pnl=('pnl','mean')))
print(a.groupby(pd.cut(a.dd,[-1,2,4,7,10,40])).agg(n=('yes','size'),yes=('yes','mean'),p=('p','mean'),pnl=('pnl','mean')))
