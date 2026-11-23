exec(open('replay.py').read().split("if __name__")[0])
b=joblib.load('blend.joblib')
for nm,D in [('dev',dev),('test',tst)]:
    for T in [720,480]:
        d=D[D['T']==T]; replay(d,d.p_hgb,0.02,f'{nm} HGB T={T}'); replay(d,sg(b.decision_function(np.c_[lg(d.mid),lg(d.p_hgb)])),0.02,f'{nm} blend T={T}')
