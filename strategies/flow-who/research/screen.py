"""Who moved the price: split in-window moves by flow features, measure follow/fade at next real fill after fee. Dev only.
    uv run python strategies/flow-who/research/screen.py ETH [h]
"""
import sys
import numpy as np, pandas as pd
from kalshi_lab.data.flow import load_flow
from kalshi_lab.validate import LOCKBOX_START

coin = sys.argv[1]; HS = [int(x) for x in sys.argv[2].split(",")] if len(sys.argv) > 2 else [600, 480, 360]
ser = f"KX{coin}15M"; cut = LOCKBOX_START.strftime("%Y-%m-%d")
d = pd.read_parquet(f"research/data/{ser}.parquet")
d = d[d.h.isin(HS)].copy()
d["close_s"] = d.close.astype("int64") // 10**9 if str(d.close.dtype).startswith("datetime64[ns") else d.close.astype("int64")
d["close_s"] = pd.to_datetime(d.close).astype("int64") // (10**9 if True else 1)
# datetime resolution robust
d["close_s"] = (pd.to_datetime(d.close) - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds().astype(int)

def dense(src):
    f = load_flow(src, "2025-12-01", cut, dense=True)
    t0 = int(f.t.iloc[0])
    return t0, f
t0o, fo = dense(f"okx_{coin.lower()}usdtswap"); t0b, fb = dense(f"binance_{coin.lower()}usdt")
def cs(f, c): return np.concatenate([[0.0], np.cumsum(f[c].fillna(0).to_numpy())])
O = {c: cs(fo, c) for c in ("buy", "sell", "n")}; B = {c: cs(fb, c) for c in ("buy", "sell", "n")}
mt = fo.max_trade.fillna(0).to_numpy()
# sparse table for window max of max_trade: use block approach via numpy rolling max per market (cheap enough)
op = d.close_s.to_numpy() - 900; t = d.close_s.to_numpy() - d.h.to_numpy()
def win(C, a, b, t0): 
    ia = np.clip(a - t0, 0, len(C["buy"]) - 1); ib = np.clip(b - t0, 0, len(C["buy"]) - 1)
    return {k: C[k][ib] - C[k][ia] for k in C}
wo, wb = win(O, op, t, t0o), win(B, op, t, t0b)
# half-window recent (last third of elapsed time)
rec = op + (t - op) * 2 // 3
wo2, wb2 = win(O, rec, t, t0o), win(B, rec, t, t0b)
mx = np.array([mt[max(a - t0o, 0):max(b - t0o, 1)].max() if b - t0o > 0 else 0 for a, b in zip(op, t)])
vo = wo["buy"] + wo["sell"]; vb = wb["buy"] + wb["sell"]
sg = np.sign(d.D.to_numpy())
d["perp_imb"] = (wo["buy"] - wo["sell"]) / np.maximum(vo, 1e-9) * sg
d["spot_imb"] = (wb["buy"] - wb["sell"]) / np.maximum(vb, 1e-9) * sg
d["perp_imb_rec"] = (wo2["buy"] - wo2["sell"]) / np.maximum(wo2["buy"] + wo2["sell"], 1e-9) * sg
d["bigprint"] = mx / np.maximum(vo, 1e-9)               # largest perp print as share of window volume
d["avg_size"] = vo / np.maximum(wo["n"], 1)              # mean perp trade size
d["n_rate"] = wo["n"] / np.maximum(t - op, 1)
d["perp_share"] = vo / np.maximum(vo + vb, 1e-9)
d["lead"] = d.perp_imb - d.spot_imb
d["z"] = d.D / (d.rv_60m * np.sqrt(np.maximum(900 - d.h, 1)))
d["az"] = d.z.abs()
fee = lambda p: np.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100
up = d.D > 0
# follow = buy the side the move favours: YES if D>0 else NO ; fade = opposite
d["pnl_follow"] = np.where(up, d.y - d.next_ask - fee(d.next_ask), (1 - d.y) - (1 - d.next_bid) - fee(d.next_bid))
d["pnl_fade"] = np.where(up, (1 - d.y) - (1 - d.next_bid) - fee(d.next_bid), d.y - d.next_ask - fee(d.next_ask))
d["half"] = np.where(d.close < pd.Timestamp("2026-05-01", tz="UTC"), "A", "B")
d.to_pickle(f"/tmp/who_{coin}.pkl")
big = d[(d.az > 1.5) & d.pnl_follow.notna() & d.pnl_fade.notna() & d.mid.between(0.1, 0.9)]
print(coin, "big-move rows", len(big), "per h", big.groupby("h").size().to_dict(), "markets", big.ticker.nunique())
print("overall follow/fade c:", 100*big.pnl_follow.mean(), 100*big.pnl_fade.mean())
for f in ["perp_imb", "spot_imb", "perp_imb_rec", "bigprint", "avg_size", "n_rate", "perp_share", "lead"]:
    q = big.groupby("h")[f].transform(lambda x: pd.qcut(x.rank(method="first"), 3, labels=False))
    g = big.assign(q=q).groupby(["q", "half"]).agg(n=("pnl_fade", "size"), fade=("pnl_fade", lambda x: 100*x.mean()), se=("pnl_fade", lambda x: 100*x.std()/np.sqrt(len(x))))
    print("\n", f); print(g.round(2).unstack("half"))
