exec(open('replay.py').read().split("if __name__")[0])
base=pd.read_parquet('snap_quotes.parquet').dropna(subset=['mid'])
ex={}
for D in [30,60,120]:
    x=pd.read_parquet(f'snap_quotes_d{D}.parquet')[['game_id','T','mid']].rename(columns={'mid':f'mid{D}'}); base=base.merge(x,on=['game_id','T'],how='left')
base['p_hgb']=m.predict_proba(feats(base))[:,1]
d=base[base['T'].isin([300,180,120,60])].copy()
d['ey']=d.p_hgb-d.ask-fee(d.ask); d['en']=(1-d.p_hgb)-(1-d.bid)-fee(1-d.bid)
for nm,sub in [('dev',d[d.date<'2026-01-01']),('test',d[d.date>='2026-01-01'])]:
    y=sub[(sub.ey>=.02)]; n=sub[(sub.en>=.02)&~(sub.ey>=.02)]
    for lab,z,sgn in [('buyYES',y,1),('buyNO',n,-1)]:
        print(nm,lab,len(z),'mid drift +20s,+50s,+110s (in trade direction, c):',[round(sgn*(z[f'mid{D}']-z.mid).mean()*100,2) for D in [30,60,120]],' |model-mid| mean',round((z.p_hgb-z.mid).abs().mean()*100,1))
