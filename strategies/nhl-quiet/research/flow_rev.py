"""Do retail flow bursts revert? Per market: signed taker volume in a W-minute window -> price change over the next H minutes.
Screening, dev data. usage: flow_rev.py DIR SERIES [SERIES..]"""
import sys
import numpy as np, pandas as pd
D = sys.argv[1]; SER = sys.argv[2:]
W, H = 10, 30
rows = []
for s in SER:
    df = pd.read_parquet(f"{D}/{s}.parquet", columns=["t", "p", "c", "yes", "market", "event", "exp_ns"])
    for mk, g in df.groupby("market", sort=False):
        t = g.t.values; p = g.p.values; q = np.where(g.yes.values, g.c.values, -g.c.values)
        bin_ = (t // (W * 60 * 10**9)).astype(np.int64)
        ub, idx = np.unique(bin_, return_index=True)
        # last price per bin, signed vol per bin, total vol
        sgn = np.add.reduceat(q, idx); tot = np.add.reduceat(np.abs(q), idx)
        last = p[np.r_[idx[1:] - 1, len(p) - 1]]
        # next-H return: last price of bin+H/W
        k = H // W
        nxt = pd.Series(last, index=ub).reindex(ub + k).values
        # require some trade in that bin
        r = pd.DataFrame(dict(series=s, event=g.event.iloc[0], bin=ub, sgn=sgn, tot=tot, last=last, nxt=nxt,
                              exp=g.exp_ns.iloc[0]))
        rows.append(r)
d = pd.concat(rows, ignore_index=True).dropna()
d["imb"] = d.sgn / d.tot
d["ret"] = (d.nxt - d["last"]) * 100  # cents, YES terms
d["tt"] = (d.exp - (d.bin + 1) * W * 60 * 10**9) / 3.6e12  # hours to expected expiration at window end
d["sg"] = np.sign(d.imb) * d.ret    # return in the direction of the flow
d["big"] = d.tot >= d.tot.quantile(0.9)
print(len(d), "windows;  corr(imb, ret) %.4f" % np.corrcoef(d.imb, d.ret)[0, 1])
def rep(name, m):
    x = d[m]
    if len(x) < 200: return
    a = x.groupby("event").sg.mean()
    se = a.std() / np.sqrt(len(a))
    print(f"{name:34s} n={len(x):7d} ev={len(a):5d} follow-ret {x.sg.mean():6.3f}c  (event-mean {a.mean():6.3f} se {se:.3f})")
for lo, hi in ((0.8, 1.01), (0.5, 0.8)):
    m = (d.imb.abs() >= lo) & (d.imb.abs() < hi)
    rep(f"|imb| {lo}-{hi} all", m)
    rep(f"|imb| {lo}-{hi} top-10% volume", m & d.big)
    for a, b in ((-1e3, 0), (0, 3), (3, 6), (6, 12), (12, 24), (24, 1e3)):
        rep(f"|imb| {lo}-{hi} tt {a}..{b}h", m & (d.tt >= a) & (d.tt < b))
