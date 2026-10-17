"""Sub-10s BTC->ETH/SOL lead at 1s Binance resolution (dev data only). Predict coin return [t,t+F] from BTC and own past [t-L,t]."""
import sys
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eth-overreact/research"))
from panel import load_spot
from kalshi_lab.validate import LOCKBOX_START
LB = int(LOCKBOX_START.timestamp())
Tb, sb = load_spot("binance_btcusdt")
for coin in ("eth", "sol"):
    Tc, sc = load_spot(f"binance_{coin}usdt")
    T0 = max(Tb, Tc) + 100
    t = np.arange(T0, LB - 100)
    lb = lambda x: np.log(sb[x - Tb]); lc = lambda x: np.log(sc[x - Tc])
    for L, F in ((1,1),(1,3),(2,2),(3,3),(5,5),(5,10)):
        rb = lb(t)-lb(t-L); rc = lc(t)-lc(t-L); y = lc(t+F)-lc(t)
        X = np.column_stack([np.ones(len(t)), rc, rb])
        b = np.linalg.lstsq(X, y, rcond=None)[0]
        res = y - X@b
        se = np.sqrt(np.diag(np.linalg.inv(X.T@X))*res.var())
        big = np.abs(rb) > 3*rb.std()
        g = rb-rc
        m = np.abs(g) > 3*g.std()
        print(f"{coin} L={L} F={F} btc_coef {b[2]:+.3f} (t {b[2]/se[2]:+.0f}) own {b[1]:+.3f} | big-BTC n={big.sum()} mean y*sign(rb) {1e4*np.mean(y[big]*np.sign(rb[big])):.2f}bp  gap-cond {1e4*np.mean(y[m]*np.sign(g[m])):.2f}bp (n={m.sum()}) sd(y) {1e4*y.std():.1f}bp")
