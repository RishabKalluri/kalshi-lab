"""Memory-light who-moved-the-price screen. One month at a time, dense flow only for that month (+1h warmup).
Features per (market,h) row at time t=close-h using flow rows <= t-1 (no lookahead). Dev data only.
    uv run python strategies/flow-who/research/screen2.py ETH   -> /tmp/who2_ETH.pkl"""
import sys, numpy as np, pandas as pd
from kalshi_lab.data.flow import load_flow
from kalshi_lab.validate import LOCKBOX_START
coin = sys.argv[1]; c = coin.lower(); ser = f"KX{coin}15M"; cut = pd.Timestamp(LOCKBOX_START, tz="UTC") if not hasattr(LOCKBOX_START,"tzinfo") or LOCKBOX_START.tzinfo is None else LOCKBOX_START
D = pd.read_parquet(f"research/data/{ser}.parquet")
D = D[D.close < cut].copy()
D["close_s"] = (D.close - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds().astype("int64")
D["ym"] = D.close.dt.strftime("%Y-%m")
out = []
def cs(a): return np.concatenate([[0.0], np.cumsum(a, dtype="float64")])
for ym, g in D.groupby("ym"):
    s0 = pd.Timestamp(ym + "-01", tz="UTC"); s1 = s0 + pd.offsets.MonthBegin(1)
    ld0 = (s0 - pd.Timedelta(days=1)).strftime("%Y-%m-%d"); ld1 = (s1 + pd.Timedelta(days=1)).strftime("%Y-%m-%d")
    fb = load_flow(f"binance_{c}usdt", ld0, min(ld1, cut.strftime("%Y-%m-%d")), dense=True)
    fo = load_flow(f"okx_{c}usdtswap", ld0, min(ld1, cut.strftime("%Y-%m-%d")), dense=True)
    if len(fb) < 1000 or len(fo) < 1000: continue
    t0 = int(max(fb.t.iloc[0], fo.t.iloc[0])); t1 = int(min(fb.t.iloc[-1], fo.t.iloc[-1]))
    fb = fb[(fb.t >= t0) & (fb.t <= t1)].reset_index(drop=True); fo = fo[(fo.t >= t0) & (fo.t <= t1)].reset_index(drop=True)
    n = min(len(fb), len(fo)); fb, fo = fb.iloc[:n], fo.iloc[:n]
    lp = np.log(fb.px.to_numpy()); r1 = np.diff(lp, prepend=lp[0])
    CS = {"r2": cs(r1**2)}
    for nm, f in (("o", fo), ("b", fb)):
        for k in ("buy", "sell", "n"): CS[nm + k] = cs(f[k].to_numpy())
    mt = fo.max_trade.fillna(0).to_numpy()
    plp = np.log(fo.px.ffill().bfill().to_numpy())
    g = g[(g.close_s - 900 - 3600 > t0) & (g.close_s <= t1)]
    op = g.close_s.to_numpy() - 900; t = g.close_s.to_numpy() - g.h.to_numpy()
    def W(k, a, b): return CS[k][np.clip(b - t0 + 1, 0, n)] - CS[k][np.clip(a - t0 + 1, 0, n)]   # sum rows a<t<=b, uses rows<=b
    tt = t - 1                    # last usable row
    ia, ib = op - t0, tt - t0
    sig = np.sqrt((CS["r2"][op - t0] - CS["r2"][op - t0 - 3600]) / 3600)      # per-sec sigma, hour before open
    ret = lp[ib] - lp[ia]; z = ret / (sig * np.sqrt(np.maximum(tt - op, 1)))
    pret = plp[ib] - plp[ia]
    ob, os_, on = W("obuy", op, tt), W("osell", op, tt), W("on", op, tt)
    bb, bs, bn = W("bbuy", op, tt), W("bsell", op, tt), W("bn", op, tt)
    vo, vb = ob + os_, bb + bs
    sg = np.sign(ret)
    # largest perp print in window (loop)
    mx = np.array([mt[a:b+1].max() for a, b in zip(ia, ib)])
    # volume vs trailing baseline: hour before open per second
    vo_base = (W("obuy", op - 3600, op) + W("osell", op - 3600, op)) / 3600
    # last-third imbalance
    rec = op + (tt - op) * 2 // 3
    rb, rs = W("obuy", rec, tt), W("osell", rec, tt)
    # max 30s burst of |ret| share: biggest 30s |move| / total |move| (jumpiness)
    r30 = np.abs(lp[np.minimum(ia[:,None] + np.arange(30, 900, 30)[None,:], ib[:,None]).clip(0)] - lp[np.minimum(ia[:,None] + np.arange(0, 870, 30)[None,:], ib[:,None]).clip(0)])
    gg = g.copy()
    gg["z"] = z; gg["ret_bp"] = ret * 1e4; gg["sig"] = sig
    gg["perp_imb"] = (ob - os_) / np.maximum(vo, 1e-12) * sg
    gg["spot_imb"] = (bb - bs) / np.maximum(vb, 1e-12) * sg
    gg["imb_rec"] = (rb - rs) / np.maximum(rb + rs, 1e-12) * sg
    gg["bigprint"] = mx / np.maximum(vo, 1e-12)
    gg["avg_size"] = vo / np.maximum(on, 1)
    gg["vol_rel"] = vo / np.maximum(vo_base * np.maximum(tt - op, 1), 1e-12)
    gg["n_rel"] = on / np.maximum(W("on", op - 3600, op) / 3600 * np.maximum(tt - op, 1), 1e-12)
    gg["perp_share"] = vo / np.maximum(vo + vb, 1e-12)
    gg["lead"] = (pret - ret) * sg / (sig * np.sqrt(np.maximum(tt - op, 1)))
    gg["jump"] = r30.max(1) / np.maximum(r30.sum(1), 1e-12)
    out.append(gg); print(coin, ym, len(gg), flush=True)
d = pd.concat(out)
fee = lambda p: np.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100
up = d.z > 0
d["pnl_follow"] = np.where(up, d.y - d.next_ask - fee(d.next_ask), (1 - d.y) - (1 - d.next_bid) - fee(d.next_bid))
d["pnl_fade"] = np.where(up, (1 - d.y) - (1 - d.next_bid) - fee(d.next_bid), d.y - d.next_ask - fee(d.next_ask))
d["gross_follow_mid"] = np.where(up, d.y - d.mid, (1 - d.y) - (1 - d.mid))
d.to_pickle(f"/tmp/who2_{coin}.pkl")
