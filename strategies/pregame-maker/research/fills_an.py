"""Post-hoc analysis of a backtest run dir: per-fill pnl net of the exact maker fee (the engine charges makers 0)."""
import sys, math
import numpy as np, pandas as pd

d = sys.argv[1]
f = pd.read_csv(d + "/fills.csv", parse_dates=["time"])
m = pd.read_csv(d + "/markets.csv")[["ticker", "result", "close_time", "open_time"]]
f = f.merge(m, on="ticker")
f["y"] = (f.result == "yes").astype(float)
p = f.price / 1000
f["gross"] = np.where(f.side == "sell", p - f.y, f.y - p) * f.qty        # $ per fill
f["mfee"] = np.ceil(np.round(0.0175 * f.qty * p * (1 - p) * 100, 6)) / 100
f["net"] = f.gross - f.mfee - f.fee
f["px"] = np.where(f.side == "sell", f.price, f.price)                    # YES-terms price
f["bucket"] = pd.cut(f.price, [0, 100, 200, 400, 600, 800, 900, 1000])
ev = f.ticker.str.rsplit("-", n=1).str[0]
f["event"] = ev


def boot(g, n=1000):
    # cluster bootstrap over events
    e = g.groupby("event").agg(net=("net", "sum"), q=("qty", "sum"))
    if len(e) < 5:
        return (np.nan, np.nan)
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(e), (n, len(e)))
    r = 100 * e.net.to_numpy()[idx].sum(1) / e.q.to_numpy()[idx].sum(1)
    return tuple(np.percentile(r, [2.5, 97.5]).round(2))


def line(name, g):
    q = g.qty.sum()
    print(f"{name:22s} fills {len(g):6d} ctr {q:9.0f} gross {100*g.gross.sum()/q:6.2f}c fee {100*g.mfee.sum()/q:5.2f}c "
          f"net {100*g.net.sum()/q:6.2f}c CI {boot(g)}  events {g.event.nunique()}")


line("ALL", f)
for s, g in f.groupby("side"):
    line(f"side {s}", g)
for b, g in f.groupby("bucket", observed=True):
    line(f"px {b}", g)
f["ser"] = f.ticker.str.split("-").str[0]
for b, g in f.groupby("ser"):
    line(b, g)
f["month"] = f.time.dt.strftime("%Y-%m")
for b, g in f.groupby("month"):
    line("month " + b, g)
fr = pd.read_parquet("/srv/kalshi/strategies/pregame-maker/research/frame.parquet")[["ticker", "start"]]
f = f.merge(fr, on="ticker", how="left")
f["tts_h"] = (f.start - f.time.dt.as_unit("ns").astype("int64")) / 3.6e12
f["tb"] = pd.cut(f.tts_h, [-12, 0, 1, 3, 6, 12, 24, 48, 80])
for b, g in f.groupby("tb", observed=True):
    line("tts " + str(b), g)
