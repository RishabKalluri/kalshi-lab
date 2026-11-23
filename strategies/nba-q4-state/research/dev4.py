exec(open('replay.py').read().split("if __name__")[0])
for D in [10,30,60,120]:
    S2=pd.read_parquet('snap_quotes.parquet' if D==10 else f'snap_quotes_d{D}.parquet').dropna(subset=['mid']).copy()
    S2['p_hgb']=m.predict_proba(feats(S2))[:,1]
    d=S2[(S2.date<'2026-01-01')&S2['T'].isin([300,180,120,60])]
    replay(d,d.p_hgb,0.02,f'DEV quote delay {D}s')
