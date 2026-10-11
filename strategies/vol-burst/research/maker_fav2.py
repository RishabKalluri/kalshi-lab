"""H6b: penny-jump the favourite's bid by 1c (first in queue) on the volfav signal; fill if any taker sells
within 10 s at <= our price. Compare to joining the bid and to the taker."""
import numpy as np, pandas as pd
pd.set_option("display.width", 220)
fee = lambda p: np.ceil(7 * p * (1 - p)) / 100
for series in ["KXETH15M", "KXSOL15M"]:
    d = pd.read_parquet(f"strategies/vol-burst/research/feats_{series}.parquet")
    d = d.dropna(subset=["rv_15m", "rv_60m", "rv_4h"]); d = d[(d.rv_15m > 0) & (d.rv_60m > 0) & (d.rv_4h > 0)].copy()
    d["half"] = np.where(d.close < "2026-05-01", "A", np.where(d.close < "2026-07-01", "B1", "B2")); d["utch"] = d.close.dt.hour
    X = lambda x: np.column_stack([np.ones(len(x)), np.log(x.rv_15m), np.log(x.rv_60m), np.log(x.rv_4h), np.log(x.h)] + [(x.utch == k).astype(float) for k in range(1, 24)])
    A = d[(d.half == "A") & (d.rv_fut > 0.02 * d.rv_fut.median())]
    b, *_ = np.linalg.lstsq(X(A), np.log(A.rv_fut), rcond=None); d["lr"] = np.log(d.iv / np.exp(X(d) @ b))
    fy = d.mid > 0.5; win = np.where(fy, d.y == 1, d.y == 0)
    spread = d.ask - d.bid
    pj = np.where(spread > 0.015, 0.01, 0.0)
    px = np.where(fy, d.bid + pj, 1 - (d.ask - pj))
    filled = np.where(fy, d.next_bid <= d.bid + pj + 1e-9, d.next_ask >= d.ask - pj - 1e-9)
    d["pj_pnl"] = np.where(filled, (win - px) * 100, np.nan); d["filled"] = filled
    tk = np.where(fy, d.next_ask, 1 - d.next_bid); d["tk_pnl"] = (win - tk - fee(tk)) * 100
    d["fpx"] = d.mid.where(fy, 1 - d.mid); d["spread"] = spread
    s = d[d.h.between(60, 360) & d.fpx.between(0.57, 0.93)].copy()
    s["vf"] = s.lr > s[s.half == "A"].lr.quantile(0.7)
    g = s.groupby(["vf", "half"]).agg(pj=("pj_pnl", "mean"), sd=("pj_pnl", "std"), n_fill=("pj_pnl", "count"), fill=("filled", "mean"), tk=("tk_pnl", "mean"), n=("tk_pnl", "count"), spr=("spread", "median"))
    g["t"] = g.pj / (g.sd / np.sqrt(g.n_fill))
    print(f"\n{series}: penny-jump maker vs taker, h 60-360\n", g.round(3).to_string())
