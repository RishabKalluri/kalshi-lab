"""Pool several backtest run dirs: per-fill pnl net of the exact maker fee (engine charges makers 0), cluster bootstrap by game.
usage: fills_pool.py rundir..."""
import sys
import numpy as np, pandas as pd

fs = []
for d in sys.argv[1:]:
    f = pd.read_csv(d + "/fills.csv", parse_dates=["time"])
    m = pd.read_csv(d + "/markets.csv")[["ticker", "result"]]
    f = f.merge(m, on="ticker")
    f["run"] = d.rsplit("/", 1)[-1]
    fs.append(f)
f = pd.concat(fs)
f["y"] = (f.result == "yes").astype(float)
p = f.price / 1000
f["gross"] = np.where(f.side == "sell", p - f.y, f.y - p) * f.qty
f["mfee"] = np.ceil(np.round(0.0175 * f.qty * p * (1 - p) * 100, 6)) / 100
f["net"] = f.gross - f.mfee - f.fee
f["event"] = f.ticker.str.rsplit("-", n=1).str[0]
f["ser"] = f.ticker.str.split("-").str[0]
f["month"] = f.time.dt.strftime("%Y-%m")


def boot(g, n=2000):
    e = g.groupby("event").agg(net=("net", "sum"), q=("qty", "sum"))
    if len(e) < 5:
        return (np.nan, np.nan)
    rng = np.random.default_rng(0)
    idx = rng.integers(0, len(e), (n, len(e)))
    r = 100 * e.net.to_numpy()[idx].sum(1) / e.q.to_numpy()[idx].sum(1)
    return tuple(float(x) for x in np.percentile(r, [2.5, 97.5]).round(2))


def line(name, g):
    q = g.qty.sum()
    lo, hi = boot(g)
    print(f"{name:18s} fills {len(g):6d} ctr {q:8.0f} gross {100*g.gross.sum()/q:6.2f}c fee {100*g.mfee.sum()/q:5.2f}c "
          f"net {100*g.net.sum()/q:6.2f}c CI [{lo:6.2f},{hi:6.2f}] games {g.event.nunique()}")


line("POOLED", f)
for k, g in f.groupby("month"):
    line("month " + k, g)
for k, g in f.groupby("ser"):
    line(k, g)
for k, g in f.groupby("side"):
    line("side " + k, g)
f["pb"] = pd.cut(f.price, [0, 30, 60, 100, 910, 940, 970, 1000])
for k, g in f.groupby("pb", observed=True):
    line(f"px {k}", g)
mo = f.groupby("month").net.sum()
print("months positive:", int((mo > 0).sum()), "/", len(mo))
