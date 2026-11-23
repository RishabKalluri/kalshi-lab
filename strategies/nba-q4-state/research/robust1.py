exec(open('replay.py').read().split("if __name__")[0])
b=joblib.load('blend.joblib')
base=pd.read_parquet('snap_quotes.parquet').dropna(subset=['mid']); base['p_hgb']=m.predict_proba(feats(base))[:,1]
base['p_bl']=sg(b.decision_function(np.c_[lg(base.mid),lg(base.p_hgb)]))
tr=pd.read_parquet('kal_KXNBAGAME_trades.parquet')
# capacity: same-side taker volume in 15 s after t0 (needs per-snapshot) -> recompute quickly
st=pd.read_parquet('states.parquet')[['game_id']]
sn=pd.read_parquet('snaps.parquet'); 
def tradelist(d,pcol,thr=.02):
    d=d.copy(); d['ps']=d[pcol]
    d['ey']=d.ps-d.ask-fee(d.ask); d['en']=(1-d.ps)-(1-d.bid)-fee(1-d.bid)
    ty=(d.ey>=thr)&d.ask.notna(); tn=(d.en>=thr)&d.bid.notna()&~ty
    a=d[ty].copy(); a['side']='YES'; a['px']=a.ask; a['win']=a.hw; a['cap']=a.ask_sz
    c=d[tn].copy(); c['side']='NO'; c['px']=1-c.bid; c['win']=1-c.hw; c['cap']=c.bid_sz
    t=pd.concat([a,c]); t['pnl']=t.win-t.px-fee(t.px); t['month']=t.date.str[:7]; return t
for nm,D in [('dev',base[base.date<'2026-01-01']),('test',base[base.date>='2026-01-01'])]:
    D=D[D['T'].isin([300,180,120,60])]
    for pc in ['p_hgb','p_bl']:
        t=tradelist(D,pc)
        print(nm,pc,len(t),'overall',round(t.pnl.mean()*100,2))
        print(t.groupby('month').pnl.agg(['mean','count']).round(3).T.to_string())
        t['po']=t.date>='2026-04-14'; print(t.groupby('po').pnl.agg(['mean','count']).round(3).T.to_string())
        # per-game: sum pnl at 1 contract, fraction of positive months
        g=t.groupby('game_id').pnl.sum(); print('games',len(g),'pnl/game $ per contract',round(g.mean(),3))
