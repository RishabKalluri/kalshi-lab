import pandas as pd,numpy as np
st={'ATL':'ATL','AUS':'AUS','BOS':'BOS','CHI':'ORD','DAL':'DFW','DC':'DCA','DEN':'DEN','EWR':'EWR','HOU':'IAH','LAX':'LAX','LV':'LAS','MIA':'MIA','MIN':'MSP','NOLA':'MSY','NYC':'NYC','OKC':'OKC','PHIL':'PHL','PHX':'PHX','SATX':'SAT','SEA':'SEA','SFO':'SFO','TTN':'TTN'}
D='strategies/rain-obs/research/data/'
obs={}
for c,s in st.items():
    o=pd.read_csv(D+s+'.csv',na_values=['M']);o['valid']=pd.to_datetime(o.valid)
    obs[c]=o
M=pd.read_pickle('/tmp/rain_M.pkl');T=pd.read_pickle('/tmp/rain_T.pkl')
M['city']=M.ticker.str.split('-').str[-1]
M['close_ns']=pd.to_datetime(M.close).dt.tz_localize(None).astype('datetime64[ns]').astype('int64')
M['close_dt']=pd.to_datetime(M.close).dt.tz_localize(None)
def first_rain(r):
    o=obs[r.city];s=r.close_dt-pd.Timedelta(hours=24)
    x=o[(o.valid>=s)&(o.valid<=r.close_dt)&(o.p01i>0)]
    return x.valid.min() if len(x) else pd.NaT
M['fr']=M.apply(first_rain,axis=1)
M['yes']=(M.result=='yes').astype(int);M['obs_rain']=M.fr.notna().astype(int)
print(pd.crosstab(M.yes,M.obs_rain))
M.to_pickle('/tmp/rain_M2.pkl')
def first_rain2(r,thr):
    o=obs[r.city];s=r.close_dt-pd.Timedelta(hours=24)
    x=o[(o.valid>=s)&(o.valid<=r.close_dt)&(o.p01i>=thr)]
    return x.valid.min() if len(x) else pd.NaT
M['fr2']=M.apply(lambda r:first_rain2(r,0.005),axis=1)
M['obs2']=M.fr2.notna().astype(int)
print(pd.crosstab(M.yes,M.obs2))
M.to_pickle('/tmp/rain_M2.pkl')
