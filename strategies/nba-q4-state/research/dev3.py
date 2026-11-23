exec(open('replay.py').read().split("if __name__")[0])
d=dev[dev['T'].isin([300,180,120,60])].copy()
d['ey']=d.p_hgb-d.ask-fee(d.ask); sel=d[(d.ey>=.02)]
print('selected YES trades',len(sel),'mean ask-mid',(sel.ask-sel.mid).mean(),'median ask_sz',sel.ask_sz.median(),'ask5 - ask',(sel.ask5-sel.ask).mean(), 'ask15-ask',(sel.ask15-sel.ask).mean(), 'ask_t median',sel.ask_t.median())
allq=d.dropna(subset=['ask']); print('all: ask-mid',(allq.ask-allq.mid).mean(),'ask5-ask',(allq.ask5-allq.ask).mean())
for nm,a,b in [('first print','ask','bid'),('worst in 5s','ask5','bid5'),('worst in 15s','ask15','bid15')]:
    dd=d.copy(); dd['ask']=dd[a]; dd['bid']=dd[b]
    replay(dd,dd.p_hgb,0.02,'DEV '+nm)
dd=d.copy(); dd.loc[dd.ask_sz<20,'ask']=np.nan; dd.loc[dd.bid_sz<20,'bid']=np.nan; replay(dd,dd.p_hgb,0.02,'DEV first print size>=20')
# mid-based: entry at mid+0.5c spread
dd=d.copy(); dd['ask']=dd.mid+.01; dd['bid']=dd.mid-.01; replay(dd,dd.p_hgb,0.02,'DEV entry at stale mid +-1c (no future info)')
