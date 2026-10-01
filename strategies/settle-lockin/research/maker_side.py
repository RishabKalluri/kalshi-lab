"""What does the passive side of each Kalshi trade earn (no maker fee)? By the taker's side price, time left, month.
Maker PnL per contract = taker price paid - taker's payoff."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
for series in ["KXETH15M", "KXSOL15M"]:
    df = pd.read_parquet(Path(__file__).resolve().parents[3] / "research/data/settle-lockin" / f"{series}_trades.parquet")
    df["tau"] = df.close - df.t
    df = df[(df.tau > 0) & (df.tau <= 900) & (df.close >= pd.Timestamp("2026-01-15", tz="UTC").timestamp())]
    df["month"] = pd.to_datetime(df.close, unit="s").dt.strftime("%m")
    px = np.where(df.buy, df.price, 1 - df.price)          # taker's price for its side
    win = np.where(df.buy, df.y, 1 - df.y)
    df["mk"] = (px - win) * 100                            # maker c/contract
    df["pb"] = pd.cut(px, [0, 0.1, 0.2, 0.3, 0.5, 0.7, 0.9, 1.0])
    df["tb"] = pd.cut(df.tau, [0, 60, 180, 360, 600, 900])
    print(f"===== {series}: contract-weighted maker PnL (c/ct) by taker-side price x time left")
    g = df.assign(w=df.mk * df.qty)
    pv = g.groupby(["pb", "tb"], observed=True).agg(w=("w", "sum"), q=("qty", "sum"))
    print((pv.w / pv.q).unstack().round(2).to_string())
    print("contracts (k):")
    print((pv.q / 1000).unstack().round(0).to_string())
    sel = g[(px <= 0.3)]
    m = sel.groupby("month").agg(w=("w", "sum"), q=("qty", "sum"))
    print("underdog-taker trades (<=30c): maker c/ct by month", (m.w / m.q).round(2).to_dict())
