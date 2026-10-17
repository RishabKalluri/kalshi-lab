"""Tail BTC 1-3s moves: mean continuation of ETH/SOL (bp) after |BTC r_3s| above thresholds, own move removed (dev data)."""
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
    t = np.arange(max(Tb, Tc) + 100, LB - 100)
    lb = lambda x: np.log(sb[x - Tb]); lc = lambda x: np.log(sc[x - Tc])
    L = 3
    rb = lb(t)-lb(t-L); rc = lc(t)-lc(t-L)
    for F in (1, 3, 10):
        y = lc(t+F)-lc(t)
        for q in (99, 99.9, 99.99):
            th = np.percentile(np.abs(rb), q)
            m = (np.abs(rb) >= th)
            s = np.sign(rb[m])
            lag = (rb[m]-rc[m])*s  # BTC move not yet in coin, signed
            print(f"{coin} F={F} q{q} thr {1e4*th:.1f}bp n={m.sum()} fwd {1e4*np.mean(y[m]*s):+.2f}bp  already-moved coin {1e4*np.mean(rc[m]*s):+.2f}bp  unmatched {1e4*np.mean(lag):+.2f}bp")
