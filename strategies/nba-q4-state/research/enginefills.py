import pandas as pd, glob
rows=[]
for d in sorted(glob.glob('nba-q4-state-1022-201230-wf-*')):
    f=pd.read_csv(d+'/fills.csv'); m=pd.read_csv(d+'/markets.csv')[['ticker','result']]
    f=f.merge(m,on='ticker'); f['mon']=d[-7:]
    f['y']=(f.result=='yes').astype(float); f['px']=f.price/1000
    f['win']=((f.side=='buy')&(f.y==1))|((f.side=='sell')&(f.y==0))
    f['cost']=f.px.where(f.side=='buy',1-f.px)
    f['pnl']=f.win.astype(float)-f.cost-f.fee/f.qty
    rows.append(f)
f=pd.concat(rows); f['T']=f.tag.str[3:]
print(f.groupby('mon').apply(lambda x:pd.Series(dict(n=len(x),unw_c=x.pnl.mean()*100,w_c=(x.pnl*x.qty).sum()/x.qty.sum()*100,qty=x.qty.mean()))).round(2))
print(f.groupby('T').apply(lambda x:pd.Series(dict(n=len(x),unw=x.pnl.mean()*100))).round(2))
print('overall unweighted',f.pnl.mean()*100, len(f))
