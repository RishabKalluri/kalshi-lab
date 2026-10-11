"""Screen 2a: realized vol by minute of the hour (Binance 1-s last prices from the flow files), development data.
Prints mean squared 1-minute log return per minute-of-hour relative to the hour's average, per coin and half,
and the implied vol share of each quarter-hour window."""
import sys
import numpy as np, pandas as pd
from kalshi_lab.data.flow import load_flow
from kalshi_lab.validate import LOCKBOX_START


def minute_prices(sym):
    f = load_flow(f"binance_{sym}usdt", "2025-12-10", pd.Timestamp(LOCKBOX_START).date() - pd.Timedelta(days=1))
    return f


if __name__ == "__main__":
    for sym in sys.argv[1:] or ["eth", "sol", "btc"]:
        f = minute_prices(sym)
        if sym == "eth":
            print(f.columns.tolist(), len(f))
        t = pd.to_datetime(f["t"], unit="s", utc=True)
        px = pd.Series(f["px"].values, index=t).sort_index()
        px = px[~px.index.duplicated()]
        m = px.resample("1min").last().ffill()
        r = np.log(m).diff().dropna()
        df = pd.DataFrame({"r2": r ** 2})
        df["mn"] = df.index.minute
        df["wk"] = df.index.tz_convert("America/New_York").dayofweek < 5
        df["half"] = np.where(df.index < pd.Timestamp("2026-05-01", tz="UTC"), "A", "B")
        df["hour"] = df.index.floor("h")
        df["rel"] = df.r2 / df.groupby("hour").r2.transform("mean")
        g = df.groupby(["half", "mn"]).rel.mean().unstack("half")
        print(f"\n== {sym}: mean r^2 relative to its hour, by minute of hour (minute m = return from m-1 to m)")
        print(g.T.round(2).to_string())
        q = df.assign(qtr=(df.mn - 1) % 60 // 15).groupby(["half", "qtr"]).rel.mean().unstack("half")
        print("quarter (0 = minutes 1..15 i.e. window starting :00):"); print(q.round(3).to_string())
