import pandas as pd, numpy as np
o=pd.read_pickle('/tmp/sol_trend.pkl')
def fee(p): return 0.07*p*(1-p)
def rep(name,s):
    out=[]
    for hf in (0,1):
        t=s[s.half==hf]; a=t.dropna(subset=['next_ask']); b=t.dropna(subset=['next_bid'])
        out.append((len(t), round((a.y-a.next_ask-fee(a.next_ask)).mean()*100,2), round(((1-b.y)-(1-b.next_bid)-fee(1-b.next_bid)).mean()*100,2)))
    print(name,out)
mn=o.index.minute; hr=o.index.hour
for lab,mask,f in [('hour :00 z4',mn==0,'z4'),('hour :00 z2',mn==0,'z2'),('hour :00 z8',mn==0,'z8'),('4h boundary z16',(mn==0)&(hr%4==0),'z16'),('4h bdry z8',(mn==0)&(hr%4==0),'z8'),('00UTC z32',(mn==0)&(hr==0),'z32'),('00UTC z16',(mn==0)&(hr==0),'z16'),('30min :30 z2',mn==30,'z2')]:
    s=o[mask]
    for thr in (1.0,1.5):
        rep(f'{lab} z<-{thr} (buyYES)',s[s[f]<-thr]); rep(f'{lab} z>{thr} (buyNO)',s[s[f]>thr])
