exec(open('replay.py').read().split("if __name__")[0])
mc=pd.read_parquet('mc_preds_2026_3000.parquet')
S2=S.merge(mc,on=['game_id','T']); dv=S2[S2.date<'2026-01-01']
print('DEV (Oct-Dec) log loss by T: kalshi / hgb / mc')
for T in sorted(dv['T'].unique()):
    d=dv[dv['T']==T]; print(T,len(d),round(LL(d.hw,d.mid),4),round(LL(d.hw,d.p_hgb),4),round(LL(d.hw,d.p_mc),4))
# blend slope of mc on market
from sklearn.linear_model import LogisticRegression
for T in [None,300,180,120,60]:
    d=dv if T is None else dv[dv['T']==T]; r=LogisticRegression(C=1e6).fit(np.c_[lg(d.mid),lg(d.p_mc)],d.hw); r2=LogisticRegression(C=1e6).fit(np.c_[lg(d.mid),lg(d.p_hgb)],d.hw); print('blend T',T,'mc',r.coef_.round(2),'hgb',r2.coef_.round(2))
Q=dv[dv['T'].isin([300,180,120,60])]
for thr in [0.02,0.04]:
    replay(Q,Q.p_mc,thr,f'DEV MC thr{thr}'); replay(Q,Q.p_hgb,thr,f'DEV HGB thr{thr}')
replay(dv,dv.p_mc,0.02,'DEV MC all six T')
