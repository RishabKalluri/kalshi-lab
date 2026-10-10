"""H1 screen: does the Kalshi residual move (Kalshi 60 s move minus spot-model move) revert? Dev only.
    uv run python strategies/btc-flowrev/research/screen_h1.py"""
from pathlib import Path
import numpy as np, pandas as pd
from scipy.stats import norm
from kalshi_lab.validate import LOCKBOX_START

ROOT = Path(__file__).resolve().parents[3]
LB = int(LOCKBOX_START.timestamp())
SPLIT = int(pd.Timestamp("2026-05-01", tz="UTC").timestamp())


def load():
    p = pd.read_parquet(ROOT / "research/data/btc-flowrev/flow_panel.parquet")
    p = p[p.close < LB]
    meta = pd.read_parquet(ROOT / "research/data/KXBTC15M.parquet", columns=["close", "K", "y"])
    meta["close"] = meta.close.astype("int64") // 10**3 if meta.close.dtype != "int64" else meta.close
    meta = meta.groupby("close").agg(K=("K", "first"), y=("y", "first")).reset_index()
    p = p.merge(meta, on="close", how="inner")
    z = np.load(ROOT / "research/data/eth-overreact/binance_btcusdt.npz")
    t0, px = int(z["t0"]), z["px"]
    lr = np.diff(np.log(px), prepend=np.log(px[0]))
    c2 = np.concatenate([[0], np.cumsum(lr ** 2)])
    def S(ts):
        return px[np.clip(ts - t0, 0, len(px) - 1)]
    tn = (p.close - p.h).values.astype(int)
    p["S_now"], p["S_prev"] = S(tn), S(tn - 60)
    i = np.clip(tn - t0, 3600, len(px) - 1)
    p["sig"] = np.sqrt((c2[i] - c2[i - 3600]) / 3600)  # per-second log vol
    tau_now, tau_prev = p.h + 30, p.h + 90   # +30: settlement average midpoint
    def fair(Sx, tau):
        return norm.cdf(np.log(Sx / p.K) / (p.sig * np.sqrt(tau)))
    p["fair_now"], p["fair_prev"] = fair(p.S_now, tau_now), fair(p.S_prev, tau_prev)
    p["dk"] = p.vw_now - p.vw_prev
    p["ds"] = p.fair_now - p.fair_prev
    p["res"] = p.dk - p.ds
    p["half"] = np.where(p.close < SPLIT, "A", "B")
    p["month"] = pd.to_datetime(p.close, unit="s").dt.strftime("%m")
    return p


def fee(x):
    return 0.07 * x * (1 - x)


def fade_pnl(p):
    """residual > 0 -> sell YES at next taker-sell price (the bid); < 0 -> buy YES at next taker-buy price."""
    up = p.res > 0
    pnl = np.where(up, p.ns - p.y - fee(p.ns), p.y - p.nb - fee(p.nb))
    ok = np.where(up, p.ns.notna() & (p.ns_dt < 10), p.nb.notna() & (p.nb_dt < 10))
    px = np.where(up, p.ns, p.nb)
    ok &= (px >= 0.10) & (px <= 0.90)
    return pd.Series(np.where(ok, pnl, np.nan), index=p.index)


if __name__ == "__main__":
    p = load()
    p = p.dropna(subset=["res", "sig"])
    print(len(p), "rows with residual;", p.close.nunique(), "markets")
    print("corr(dk, ds)", p[["dk", "ds"]].corr().iloc[0, 1].round(3))
    p["fade"] = fade_pnl(p)
    p["ares"] = p.res.abs()
    # informativeness: does residual predict y beyond the current price?
    for half in "AB":
        q = p[(p.half == half)].dropna(subset=["last"])
        X = np.column_stack([np.ones(len(q)), q["last"], q.res, q.ds])
        yv = (q.y - q["last"]).values
        b, *_ = np.linalg.lstsq(X, yv, rcond=None)
        e = yv - X @ b
        cov = np.linalg.inv(X.T @ X) * e.var() * 6  # x6: ~rows per market (crude cluster inflation)
        print(half, "y - last ~ 1, last, res, ds: coefs", b.round(3), "t", (b / np.sqrt(np.diag(cov))).round(1))
    p["q"] = p.groupby("h").ares.transform(lambda x: pd.qcut(x.rank(method="first"), 5, labels=False))
    t = p.groupby(["q", "half"]).fade.agg(["mean", "sem", "count"]).unstack()
    print("\nfade PnL ($/ct) by |res| quintile (per h), A/B\n", (t * [100, 100, 1, 100, 100, 1]).round(2))
    top = p[p.q == 4]
    print("\ntop quintile by h\n", (top.groupby(["h", "half"]).fade.agg(["mean", "count"]).unstack() * [100, 100, 1, 1]).round(2))
    print("\ntop quintile by month\n", (top.groupby("month").fade.mean() * 100).round(2).to_dict())
    print("\ntop quintile, residual sign vs flow sign agreement")
    top = top.assign(agree=np.sign(top.res) == np.sign(top.f60))
    print((top.groupby(["agree", "half"]).fade.agg(["mean", "count"]).unstack() * [100, 100, 1, 1]).round(2))
