exec(open('diag1.py').read().split("for nm,D in")[0])
t=pd.concat([trades(dev[dev['T'].isin([300,180,120,60])]),trades(tst[tst['T'].isin([300,180,120,60])])])
t['grp']=np.where(t.ttype.str.contains('Free Throw'),'FT',np.where(t.ttype.str.contains('Foul'),'Foul',np.where(t.ttype.str.contains('Rebound'),'Reb',np.where(t.ttype.str.contains('Timeout|timeout'),'TO',np.where(t.ttype.str.contains('Substitution'),'Sub','shot/other')))))
print(t.groupby('grp').agg(n=('pnl','size'),pnl=('pnl','mean'),win=('win','mean'),px=('px','mean')).round(3))
print(t.ttype.value_counts().head(15))
al=pd.concat([dev,tst]); al=al[al['T'].isin([300,180,120,60])]
print(al.ttype.value_counts().head(12))
