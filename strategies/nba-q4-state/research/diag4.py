exec(open('replay.py').read().split("if __name__")[0])
al=pd.concat([dev.assign(per='dev'),tst.assign(per='test')]); al=al[al['T'].isin([300,180,120,60])].copy()
al['res']=al.hw-al.mid; al['mh']=al.p_hgb-al.mid
print(al.groupby(['per','pos']).agg(n=('res','size'),res=('res','mean'),mh=('mh','mean')).round(3))
al['pace']=al.tot/(2880-al.sec+1)*48; al['pb']=pd.qcut(al.pace,4)
print(al.groupby(['per','pb']).agg(n=('res','size'),res=('res','mean'),mh=('mh','mean')).round(3))
al['mb']=pd.cut(al.mid,[0,.1,.3,.5,.7,.9,1])
print(al.groupby(['per','mb']).agg(n=('res','size'),res=('res','mean'),mh=('mh','mean')).round(3))
# regression of res on mh
for per in ['dev','test']:
    d=al[al.per==per]; b=np.polyfit(d.mh,d.res,1); print(per,'slope res~mh',b.round(3),'corr',d[['res','mh']].corr().iloc[0,1].round(3))
