"""H3 (jumps): does the jump share of trailing vol predict lower future vol than HAR / is the favourite cheap after
jump-driven vol?  H4 (skew): does realized skewness / the sign of the biggest jump predict direction?"""
import sys, numpy as np, pandas as pd
pd.set_option("display.width", 220)
fee = lambda p: np.ceil(7 * p * (1 - p)) / 100
for series in sys.argv[1:]:
    d = pd.read_parquet(f"strategies/vol-burst/research/feats_{series}.parquet")
    d = d.dropna(subset=["rv_15m", "rv_60m", "rv_4h", "bv_15m", "bv_60m"])
    d = d[(d.rv_15m > 0) & (d.rv_60m > 0) & (d.rv_4h > 0) & (d.bv_15m > 0) & (d.bv_60m > 0)].copy()
    d["half"] = np.where(d.close < "2026-05-01", "A", "B")
    d["utch"] = d.close.dt.hour
    base = lambda x: [np.ones(len(x)), np.log(x.rv_15m), np.log(x.rv_60m), np.log(x.rv_4h), np.log(x.h)] + [(x.utch == k).astype(float) for k in range(1, 24)]
    XH = lambda x: np.column_stack(base(x))
    XJ = lambda x: np.column_stack(base(x) + [np.log(x.bv_15m), np.log(x.bv_60m), x.jump_15m, x.jump_60m])
    A = d[(d.half == "A") & (d.rv_fut > 0.02 * d.rv_fut.median())]; B = d[(d.half == "B") & (d.rv_fut > 0.02 * d.rv_fut.median())]
    for nm, X in [("HAR", XH), ("HAR+CJ", XJ)]:
        b, *_ = np.linalg.lstsq(X(A), np.log(A.rv_fut), rcond=None)
        res = np.log(B.rv_fut) - X(B) @ b
        print(series, nm, "OOS R2", round(1 - res.var() / np.log(B.rv_fut).var(), 4), "coef tail", b[-4:].round(3) if nm != "HAR" else "")
        d[f"fc_{nm}"] = np.exp(X(d) @ b)
    # favourite PnL at next fill by jump share, h 60-360, fav 55-90c
    fav_yes = d.mid > 0.5
    fpx = np.where(fav_yes, d.next_ask, 1 - d.next_bid); win = np.where(fav_yes, d.y == 1, d.y == 0)
    d["fav_px"] = fpx; d["fav_pnl"] = (win - fpx - fee(fpx)) * 100
    dpx = np.where(~fav_yes, d.next_ask, 1 - d.next_bid)
    d["dog_pnl"] = ((~win) - dpx - fee(dpx)) * 100; d["dog_px"] = dpx
    s = d[d.h.between(60, 360) & (d.fav_px >= 0.55) & (d.fav_px <= 0.92)].dropna(subset=["fav_pnl"]).copy()
    s["lr"] = np.log(s.iv / s.fc_HAR)
    s["q"] = pd.qcut(s.jump_15m, 5, labels=False)
    s["vf"] = s.lr > s.lr.quantile(0.7)
    print(f"\n{series} fav c/ct by jump_15m quintile x volfav-signal (h 60-360)")
    print(s.groupby(["q", "vf", "half"]).fav_pnl.agg(["mean", "count"]).unstack().round(2).to_string())
    # H4: direction. signed future move in sigma units vs skew/maxjump/returns
    sig = d.rv_15m * np.sqrt(d.h)
    d["zf"] = d.move_fut / sig
    for f in ["rskew_15m", "rskew_60m", "maxj_15m", "ret_15m", "ret_60m"]:
        print(series, "corr(zf,", f, ") A/B:", [round(d[d.half == hh][["zf", f]].corr().iloc[0, 1], 4) for hh in "AB"])
    # skew-signed side PnL: buy the side opposite to skew (high skew -> lower future return), any mid 15-85
    s = d[d.h.between(120, 840) & d.mid.between(0.15, 0.85)].copy()
    s["q"] = pd.qcut(s.rskew_60m, 10, labels=False)
    up = (s.y - s.next_ask - fee(s.next_ask)) * 100; dn = (s.next_bid - s.y - fee(1 - s.next_bid)) * 100
    s["yes"] = up; s["no"] = dn
    print(f"\n{series} buy-YES / buy-NO c/ct by rskew_60m decile")
    print(s.groupby(["q", "half"])[["yes", "no"]].mean().unstack().round(2).to_string())
