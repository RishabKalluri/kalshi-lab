"""Big Kalshi taker prints: does copying (or fading) them make money at the next real fill after fees?
    uv run python strategies/settle-lockin/research/big_prints.py KXETH15M"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
series = sys.argv[1]
df = pd.read_parquet(Path(__file__).resolve().parents[3] / "research/data/settle-lockin" / f"{series}_trades.parquet")
df = df[df.close >= 0].sort_values(["ticker", "t"]).reset_index(drop=True)
df["tau"] = df.close - df.t
df["half"] = np.where(df.close < pd.Timestamp("2026-05-01", tz="UTC").timestamp(), "A", "B")
fee = lambda P: 0.07 * P * (1 - P)
# next same-side and opposite-side trade price within [t+1, t+10] (taker fill after latency)
for side_name, want in [("same", None), ("opp", None)]:
    pass
nxt_buy = np.full(len(df), np.nan); nxt_sell = np.full(len(df), np.nan)
for tk, g in df.groupby("ticker", sort=False):
    idx = g.index.values; t = g.t.values; p = g.price.values; b = g.buy.values
    for flag, out in [(True, nxt_buy), (False, nxt_sell)]:
        tt, pp = t[b == flag], p[b == flag]
        if len(tt) == 0:
            continue
        j = np.searchsorted(tt, t + 1.0)
        ok = j < len(tt)
        jj = np.where(ok, j, 0)
        good = ok & (tt[jj] <= t + 10)
        out[idx[good]] = pp[jj[good]]
df["nb"], df["ns"] = nxt_buy, nxt_sell
# copy: if the big print bought YES, buy YES at next taker-buy price; else buy NO at 1 - next taker-sell price
df["copy_px"] = np.where(df.buy, df.nb, 1 - df.ns)
df["fade_px"] = np.where(df.buy, 1 - df.ns, df.nb)
win_copy = np.where(df.buy, df.y, 1 - df.y)
df["copy_pnl"] = (win_copy - df.copy_px - fee(df.copy_px)) * 100
df["fade_pnl"] = ((1 - win_copy) - df.fade_px - fee(df.fade_px)) * 100
df["notional"] = df.qty * np.where(df.buy, df.price, 1 - df.price)
q = df[df.half == "A"].notional.quantile([0.5, 0.9, 0.99, 0.999])
print(series, "notional quantiles (half A):", q.round(1).to_dict())
d = df[(df.tau > 10) & (df.tau < 900)]
d["sz"] = pd.cut(d.notional, [0, q[0.5], q[0.9], q[0.99], q[0.999], np.inf], labels=["<p50", "p50-90", "p90-99", "p99-99.9", ">p99.9"])
d["tb"] = pd.cut(d.tau, [10, 60, 180, 420, 900])
d["taker_px"] = np.where(d.buy, d.price, 1 - d.price)  # price the big taker paid for its side
d["pb"] = pd.cut(d.taker_px, [0, 0.2, 0.5, 0.8, 1.0], labels=["dog<20", "20-50", "50-80", "fav>80"])
for col in ["copy_pnl", "fade_pnl"]:
    print(f"\n{col} by size x half (c/contract), n")
    print(d.pivot_table(index="sz", columns="half", values=col, aggfunc=["mean", "count"], observed=True).round(2).to_string())
big = d[d.notional >= q[0.99]]
print("\nbig (>=p99): copy pnl by time-left x side price x half")
print(big.pivot_table(index=["tb", "pb"], columns="half", values="copy_pnl", aggfunc=["mean", "count"], observed=True).round(2).to_string())
