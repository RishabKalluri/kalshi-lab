"""Deep favourites (80-97c) at the next real fill after fee, by h, band and calm-ness (rv_5m/rv_60m)."""
import numpy as np, pandas as pd
pd.set_option("display.width", 220)
fee = lambda p: np.ceil(7 * p * (1 - p)) / 100
for series in ["KXETH15M", "KXSOL15M", "KXBTC15M"]:
    d = pd.read_parquet(f"research/data/{series}.parquet"); d = d[d.close < "2026-08-20"].copy()
    d["half"] = np.where(d.close < "2026-05-01", "A", "B")
    fy = d.mid > 0.5
    px = np.where(fy, d.next_ask, 1 - d.next_bid); win = np.where(fy, d.y == 1, d.y == 0)
    d["px"] = px; d["pnl"] = (win - px - fee(px)) * 100
    s = d[(d.px >= 0.80) & (d.px <= 0.97)].dropna(subset=["pnl"]).copy()
    s["band"] = pd.cut(s.px, [0.795, 0.85, 0.90, 0.94, 0.97])
    s["hb"] = pd.cut(s.h, [0, 90, 180, 360, 600, 900])
    print(f"\n{series} deep fav c/ct by h x band")
    print(s.groupby(["hb", "band", "half"], observed=True).pnl.agg(["mean", "count"]).unstack().round(2).to_string())
    s["calm"] = pd.qcut(s.rv_5m / s.rv_60m, 3, labels=["calm", "mid", "hot"])
    print(s.groupby(["calm", "half"], observed=True).pnl.agg(["mean", "count", "std"]).unstack().round(2).to_string())
