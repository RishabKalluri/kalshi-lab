exec(open('robust1.py').read().split("for nm,D in")[0])
def bankroll(t,cap=100,frac=0.25,start=1000.,seed=0,boot=2000):
    t=t.sort_values(['date','game_id','T']).copy()
    # per-game: process snapshots in order; bet = min(cap, frac*kelly*bankroll/price, 2% of bankroll per bet, first-print size)
    def run(order_games):
        b=start
        for g in order_games:
            x=t[t.game_id==g]
            for r in x.itertuples():
                p=r.px; q=min(cap,0.02*b/p,r.cap if r.cap==r.cap else 0)
                if q<1: continue
                b+=q*r.pnl
        return b
    games=list(dict.fromkeys(t.game_id)); end=run(games)
    rng=np.random.default_rng(seed); gx={g:t[t.game_id==g] for g in games}
    ends=[]
    for _ in range(300):
        s=rng.choice(len(games),len(games)); b=start
        for i in s:
            for r in gx[games[i]].itertuples():
                p=r.px; q=min(cap,0.02*b/p,r.cap if r.cap==r.cap else 0)
                if q>=1: b+=q*r.pnl
        ends.append(b)
    return end,np.percentile(ends,[2.5,50,97.5]),np.mean(np.array(ends)>start)
for nm,D in [('dev',base[base.date<'2026-01-01']),('test',base[base.date>='2026-01-01'])]:
    t=tradelist(D[D['T'].isin([300,180,120,60])],'p_hgb')
    for cap in [50,100,200]:
        end,ci,pu=bankroll(t,cap); print(nm,'cap',cap,'start $1000 end',round(end),'95% range',ci.round(),'P(up)',round(pu,3))
