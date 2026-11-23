exec(open('robust1.py').read().split("for nm,D in")[0])
b=joblib.load('blend.joblib')
for nm,D in [('dev',base[base.date<'2026-01-01']),('test',base[base.date>='2026-01-01'])]:
    D=D[D['T'].isin([300,180,120,60])]
    for pc in ['p_hgb','p_bl']:
        t=tradelist(D,pc)
        for capn in [25,50,100,200]:
            q=np.minimum(t.cap.fillna(0),capn); tot=(t.pnl*q).sum(); print(nm,pc,'cap',capn,'trades',len(t),'avg contracts',round(q.mean(),1),'total $',round(tot),'weighted c/ct',round(tot/q.sum()*100,2))
