"""H6 screen: join the favourite's bid (maker, no fee) instead of taking the ask, all favourites and the
volfav-signal subset. Fill proxy: a taker trades through our price within 10 s (next_bid <= bid for YES)."""
import numpy as np, pandas as pd
pd.set_option("display.width", 220)
fee = lambda p: np.ceil(7 * p * (1 - p)) / 100
for series in ["KXETH15M", "KXSOL15M"]:
    d = pd.read_parquet(f"strategies/vol-burst/research/feats_{series}.parquet")
    d = d.dropna(subset=["rv_15m", "rv_60m", "rv_4h"]); d = d[(d.rv_15m > 0) & (d.rv_60m > 0) & (d.rv_4h > 0)].copy()
    d["half"] = np.where(d.close < "2026-05-01", "A", "B"); d["utch"] = d.close.dt.hour
    X = lambda x: np.column_stack([np.ones(len(x)), np.log(x.rv_15m), np.log(x.rv_60m), np.log(x.rv_4h), np.log(x.h)] + [(x.utch == k).astype(float) for k in range(1, 24)])
    A = d[(d.half == "A") & (d.rv_fut > 0.02 * d.rv_fut.median())]
    b, *_ = np.linalg.lstsq(X(A), np.log(A.rv_fut), rcond=None); d["lr"] = np.log(d.iv / np.exp(X(d) @ b))
    fy = d.mid > 0.5
    win = np.where(fy, d.y == 1, d.y == 0)
    mk_px = np.where(fy, d.bid, 1 - d.ask)                       # our resting price for the favourite
    filled = np.where(fy, d.next_bid <= d.bid, d.next_ask >= d.ask)  # NaN compare -> False
    tk_px = np.where(fy, d.next_ask, 1 - d.next_bid)
    d["mk_pnl"] = np.where(filled, (win - mk_px) * 100, np.nan)
    d["tk_pnl"] = (win - tk_px - fee(tk_px)) * 100
    d["filled"] = filled; d["fpx"] = (d.mid.where(fy, 1 - d.mid))
    s = d[d.h.between(60, 600) & d.fpx.between(0.57, 0.90)].copy()
    thr = s[s.half == "A"].lr.quantile(0.7)
    s["vf"] = s.lr > thr
    s["hb"] = pd.cut(s.h, [0, 180, 360, 600])
    g = s.groupby(["vf", "hb", "half"], observed=True).agg(mk=("mk_pnl", "mean"), n_fill=("mk_pnl", "count"), fill=("filled", "mean"), tk=("tk_pnl", "mean"), n=("tk_pnl", "count"))
    print(f"\n{series}: maker vs taker favourite, c/ct\n", g.unstack().round(2).to_string())
