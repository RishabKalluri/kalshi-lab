exec(open('replay.py').read().split("if __name__")[0])
b=joblib.load('blend.joblib')
t=tst.copy(); print('TEST games',t.game_id.nunique())
print('LL by T on test: kalshi vs hgb')
for T in sorted(t['T'].unique()):
    d=t[t['T']==T]; print(T,len(d),round(LL(d.hw,d.mid),4),round(LL(d.hw,d.p_hgb),4))
R=t[t['T'].isin([300,180,120,60])]
replay(R,R.p_hgb,0.02,'TEST PRIMARY rule R (T 300-60)')
for T in [300,180,120,60]:
    replay(R[R['T']==T],R[R['T']==T].p_hgb,0.02,f'  T={T}')
replay(t,t.p_hgb,0.02,'TEST all six T')
for lim in [20]:
    dd=R.copy(); dd.loc[dd.ask_t>lim,'ask']=np.nan; dd.loc[dd.bid_t>lim,'bid']=np.nan
    replay(dd,dd.p_hgb,0.02,'TEST R fill<=20s')
X=np.c_[lg(t.mid),lg(t.p_hgb)]; replay(t,sg(b.decision_function(X)),0.02,'TEST blend B all T')
replay(R,sg(b.decision_function(np.c_[lg(R.mid),lg(R.p_hgb)])),0.02,'TEST blend B T300-60')
