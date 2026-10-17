"""H2: does a BTC spot move over [t-L,t] (beyond the coin's own) predict the coin's Kalshi price change to the next
trade within F s, at real prints? For each Kalshi taker-buy print at t (a fill a strategy could get), side = sign of
(btc_ret - beta*coin_ret) over L; markout = (price of the next taker print within F s) - fill, signed by side, in cents,
then minus fee. Dev data only. uv run python strategies/btc-lead/research/kalshi_markout.py KXETH15M"""
import sys
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eth-overreact/research"))
from panel import load_spot
series = sys.argv[1]; coin = {"KXETH15M": "eth", "KXSOL15M": "sol"}[series]
Tb, sb = load_spot("binance_btcusdt"); Tc, sc = load_spot(f"binance_{coin}usdt")
tr = pd.read_parquet(Path(__file__).parent / "data" / f"{series}_trades.parquet").sort_values(["ticker", "t"], kind="stable")
tr = tr[(tr.t > max(Tb, Tc) + 100)]
ts = tr.t.to_numpy(); sec = np.floor(ts).astype(int)
lb = lambda x: np.log(sb[x - Tb]); lc = lambda x: np.log(sc[x - Tc])
tk = tr.ticker.to_numpy(); p = tr.price.to_numpy() * 100; buy = tr.buy.to_numpy()
left = tr.close.to_numpy() - ts
fee = lambda q: np.ceil(7 * q * (100 - q) / 100) / 100 * 100 / 100  # cents approx: 0.07*P*(1-P) in dollars->cents
fee = lambda q: 0.07 * q * (100 - q) / 100
out = []
for L in (3, 10, 30):
    rb = lb(sec) - lb(sec - L); rc = lc(sec) - lc(sec - L)
    g = (rb - rc) * 1e4
    for F in (10, 30):
        # next print (same ticker, any side) at least 0.3s later and within F: use its price as exit mark
        j = np.arange(len(ts)) + 1
        j = np.minimum(j, len(ts) - 1)
        # find first print >= t+0.3 within same ticker
        k = np.searchsorted(ts, ts + 0.3)
        k = np.minimum(k, len(ts) - 1)
        ok = (tk[k] == tk) & (ts[k] <= ts + F) & (left > 20) & (p > 10) & (p < 90)
        for th in (2, 5, 10):
            m = ok & (np.abs(g) > th)
            # BTC up beyond coin => coin YES up => buy YES now (taker buy prints reveal ask); BTC down => sell (buy NO) at bid print
            up = g > 0
            use = m & ((up & buy) | (~up & ~buy))
            mark = np.where(up, p[k] - p, p - p[k])
            mm = mark[use]
            if len(mm) < 50: continue
            f = fee(p[use])
            net = mm - f
            out.append((L, F, th, use.sum(), mm.mean(), net.mean(), net.std() / np.sqrt(len(net))))
            print(f"{series} L={L} F={F} thr={th}bp n={use.sum()} gross {mm.mean():+.2f}c net(after taker fee) {net.mean():+.2f}c se {net.std()/np.sqrt(len(net)):.2f}")
