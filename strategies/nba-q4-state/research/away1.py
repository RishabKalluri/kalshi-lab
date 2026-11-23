exec(open('replay.py').read().split("if __name__")[0])
A=pd.read_parquet('snap_quotes_away.parquet').dropna(subset=['mid']).copy(); A['p_hgb']=m.predict_proba(feats(A))[:,1]
for nm,D in [('dev',A[A.date<'2026-01-01']),('test',A[A.date>='2026-01-01'])]:
    D=D[D['T'].isin([300,180,120,60])]; replay(D,D.p_hgb,0.02,f'{nm} rule R using AWAY market prints')
