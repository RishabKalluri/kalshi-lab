exec(open('replay.py').read().split("if __name__")[0])
d=dev.copy()
for lim in [60,20,8]:
    dd=d.copy(); dd.loc[dd.ask_t>lim,'ask']=np.nan; dd.loc[dd.bid_t>lim,'bid']=np.nan
    replay(dd,dd.p_hgb,0.02,f'DEV hgb fill<={lim}s')
for T in sorted(d['T'].unique()):
    replay(d[d['T']==T],d[d['T']==T].p_hgb,0.02,f'DEV hgb T={T}')
# directional split
x=d.copy(); x['edge_yes']=x.p_hgb-x.ask-fee(x.ask)
print('mean realized when buying yes', ((x.hw-x.ask-fee(x.ask))[x.edge_yes>=.02]).agg(['mean','count']).values)
