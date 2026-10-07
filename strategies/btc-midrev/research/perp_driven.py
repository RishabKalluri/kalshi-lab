"""H3 screen: split H1/H2 triggers by OKX BTC perp taker imbalance over the 300 s before the open. Dev only.

    uv run python strategies/btc-midrev/research/perp_driven.py
"""
import contextlib
import io
import runpy
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from kalshi_lab.data.flow import load_flow
from kalshi_lab.validate import LOCKBOX_START

HERE = Path(__file__).parent
sys.argv = ["x", "KXBTC15M"]
with contextlib.redirect_stdout(io.StringIO()):
    g = runpy.run_path(str(HERE / "late_screen.py"))
d, late, basket, fee = g["d"], g["late"], g["basket"], g["fee"]
f = load_flow("okx_btcusdtswap", "2025-12-01", LOCKBOX_START.strftime("%Y-%m-%d"), dense=True)
t0 = int(f.t.iloc[0])
cb = np.concatenate([[0.0], np.cumsum(f.buy.to_numpy())])
cs = np.concatenate([[0.0], np.cumsum(f.sell.to_numpy())])
op = d.close.to_numpy().astype(int) - 900
i = np.clip(op - t0, 300, len(f) - 1)
ok = (op - t0 >= 300) & (op - t0 < len(f))
B, S = cb[i] - cb[i - 300], cs[i] - cs[i - 300]
d["imb"] = np.where(ok & (B + S > 0), (B - S) / np.maximum(B + S, 1e-9), np.nan)
d["simb"] = d.imb * np.sign(d.btc_z300)  # > 0: perp takers pushed the same way as the late move


def run(mask, lab):
    e = d[mask].copy()
    up = e.btc_z900 < 0
    e["pnl"] = np.where(up, e.y - e.next_ask - fee(e.next_ask), e.next_bid - e.y - fee(e.next_bid))
    e = e.dropna(subset=["pnl", "simb"]).sort_values("h", ascending=False).groupby("ticker").head(1)
    med = e.simb.median()
    print(f"{lab}: median signed imbalance {med:+.3f}, n {len(e)}")
    for name, sub in (("perp-driven", e[e.simb > med]), ("rest", e[e.simb <= med])):
        gg = sub.groupby("half").pnl.agg(c=lambda x: 100 * x.mean(), se=lambda x: 100 * x.std() / np.sqrt(len(x)), n="size")
        print(f"   {name:12s} " + "  ".join(f"{h} {gg.loc[h,'c']:+.2f} (se {gg.loc[h,'se']:.2f}, n {int(gg.loc[h,'n'])})" for h in gg.index))


run(late, "H1 BTC late-confirmed")
run(basket, "H2 basket late-confirmed")
