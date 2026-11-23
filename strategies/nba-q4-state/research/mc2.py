from mcsim import *
sn=pd.read_parquet('snaps.parquet'); s=Sim(2024)
x=sn[sn.season==2026].reset_index(drop=True)
x['p_mc']=s.run(x.sec.values,x['diff'].values,x.pos.values,x.em.values,nsim=3000,seed=7,chunk=1500)
x[['game_id','T','p_mc']].to_parquet('mc_preds_2026_3000.parquet'); print('done')
