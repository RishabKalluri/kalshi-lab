"""H1 screen: does the Kalshi price over/under-react to spot moves? Development data only.

    uv run python strategies/eth-overreact/research/react_screen.py [SERIES] [LAG]

gap = z_now - z_just, where z_just is the price a minute ago (z = Phi^-1(mid)) delta-updated by the spot move
since, at vol sigma = rv_15m: z_just = (z_then * s * sqrt(tau_then) + dS) / (s * sqrt(tau_now)), tau = h - 40.
gap > 0: the market moved further toward YES than spot justifies.
PnL per contract at the next real fill after the taker fee, for buying YES (at next_ask) and selling YES (at
next_bid), by gap decile (cut on Jan-Apr), split Jan-Apr / May-Aug.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
L = int(sys.argv[2]) if len(sys.argv) > 2 else 60
d = pd.read_parquet(ROOT / f"research/data/eth-overreact/{series}_panel.parquet")
d = d[(d.h <= 840) & (d.h >= 60)]
d["mid"] = (d.ask + d.bid) / 2
d["mid_then"] = (d[f"ask_{L}"] + d[f"bid_{L}"]) / 2
ok = (d.age_ask <= 60) & (d.age_bid <= 60) & (d.ask >= d.bid) & (d[f"ask_{L}"] >= d[f"bid_{L}"])
ok &= d.mid.between(0.05, 0.95) & d.mid_then.between(0.05, 0.95) & (d.rv_15m > 0)
d = d[ok].copy()
tn = np.sqrt(np.maximum(d.h - 40, 5))
tt = np.sqrt(np.maximum(d.h + L - 40, 5))
z_now, z_then = norm.ppf(d.mid), norm.ppf(d.mid_then)
dS = d.S - d[f"S_{L}"]
s = d.rv_15m
d["z_just"] = (z_then * s * tt + dS) / (s * tn)
d["gap"] = z_now - d.z_just
d["dz_mkt"] = z_now - z_then
d["dz_spot"] = d.z_just - z_then
fee = lambda p: 0.07 * p * (1 - p)
d["pnl_buy"] = d.y - d.next_ask - fee(d.next_ask)
d["pnl_sell"] = d.next_bid - d.y - fee(d.next_bid)
d["half"] = np.where(pd.to_datetime(d.close, unit="s") < "2026-05-01", "A", "B")
print(series, "lag", L, "rows", len(d))
print("corr dz_mkt vs dz_spot", np.corrcoef(d.dz_mkt, d.dz_spot)[0, 1].round(3))
qs = d[d.half == "A"].gap.quantile(np.linspace(0, 1, 11)).to_numpy().copy()
qs[0], qs[-1] = -np.inf, np.inf
d["dec"] = pd.cut(d.gap, qs, labels=False)
for hb, sub in [("all", d), ("h>=480", d[d.h >= 480]), ("h 180-450", d[(d.h < 480) & (d.h >= 180)]),
                ("h<180", d[d.h < 180])]:
    t = sub.groupby(["dec", "half"]).agg(n=("pnl_buy", "size"), gap=("gap", "mean"),
                                         buy=("pnl_buy", "mean"), nb=("pnl_buy", "count"),
                                         sell=("pnl_sell", "mean"), ns=("pnl_sell", "count")).unstack("half")
    print(f"\n== {hb}: PnL per contract in cents (buy YES at next ask / sell YES at next bid, after fee)")
    out = pd.DataFrame({"gap": t[("gap", "A")].round(2),
                        "buyA": (100 * t[("buy", "A")]).round(2), "buyB": (100 * t[("buy", "B")]).round(2),
                        "sellA": (100 * t[("sell", "A")]).round(2), "sellB": (100 * t[("sell", "B")]).round(2),
                        "nA": t[("nb", "A")], "nB": t[("nb", "B")]})
    print(out.to_string())
