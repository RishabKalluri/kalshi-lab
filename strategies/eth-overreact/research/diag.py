"""Diagnose fit_screen vs reversal_stats: z from strikes vs Binance, |z| filter, first-checkpoint selection."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
from panel import load_spot  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
series = sys.argv[1] if len(sys.argv) > 1 else "KXETH15M"
d = pd.read_parquet(ROOT / f"research/data/eth-overreact/{series}_panel.parquet")
T0, s = load_spot(f"binance_{series[2:5].lower()}usdt")
K = d.groupby("close").K.first()
d["K_prev"] = (d.close - 900).map(K)
d["zK"] = (d.K - d.K_prev) / (d.rv_60m * 30)
cl = d.close.to_numpy()
A = lambda c: np.array([s[x - 60 - T0: x - T0].mean() for x in c])
u = np.unique(cl)
Am = dict(zip(u, (A(u - 900) - A(u - 1800))))
d["zB"] = d.close.map(Am) / (d.rv_60m * 30)
m1 = d.groupby("close").first()
print("corr zK vs zB:", m1[["zK", "zB"]].corr().iloc[0, 1].round(3), " missing zK:", m1.zK.isna().mean().round(3))
print("sign corr y vs zK:", np.corrcoef(m1.dropna(subset=["zK"]).y * 2 - 1, np.sign(m1.dropna(subset=["zK"]).zK))[0, 1].round(4),
      " vs zB:", np.corrcoef(m1.dropna(subset=["zB"]).y * 2 - 1, np.sign(m1.dropna(subset=["zB"]).zB))[0, 1].round(4))
fee = lambda p: 0.07 * p * (1 - p)
d["mid"] = (d.ask + d.bid) / 2
d["half"] = np.where(pd.to_datetime(d.close, unit="s") < "2026-05-01", "A", "B")
base = d[(d.h >= 780) & d.mid.between(0.3, 0.7) & (d.age_ask <= 120) & (d.age_bid <= 120)]
for zc in ["zB", "zK"]:
    for thr in (0.5, 1.0, 1.5, 2.0):
        e = base[base[zc].abs() > thr].copy()
        e["pnl"] = np.where(e[zc] < 0, e.y - e.next_ask - fee(e.next_ask), e.next_bid - e.y - fee(e.next_bid))
        e = e.dropna(subset=["pnl"])
        f = e.sort_values(["ticker", "h"], ascending=[True, False]).groupby("ticker").head(1)
        r = [f"{zc} |z|>{thr}: all-rows"]
        for nm, x in [("rows", e), ("first", f)]:
            g = x.groupby("half").pnl.agg(["mean", "count"])
            r.append(f"{nm} A {100 * g.loc['A', 'mean']:+.2f} ({g.loc['A', 'count']}) B {100 * g.loc['B', 'mean']:+.2f} ({g.loc['B', 'count']})")
        print(" | ".join(r))
