"""Per-window PnL of a nhl-quiet run (net of the engine's maker fee), clustered by game.
usage: fills_win.py windows.pkl rundir..."""
import sys
import numpy as np, pandas as pd
W = pd.read_pickle(sys.argv[1]).set_index("event")
fs = []
for d in sys.argv[2:]:
    f = pd.read_csv(d + "/fills.csv", parse_dates=["time"])
    m = pd.read_csv(d + "/markets.csv")[["ticker", "result"]]
    fs.append(f.merge(m, on="ticker").assign(run=d.rsplit("/", 1)[-1]))
f = pd.concat(fs)
f["y"] = (f.result == "yes").astype(float)
p = f.price / 1000
f["gross"] = np.where(f.side == "sell", p - f.y, f.y - p) * f.qty
f["net"] = f.gross - f.fee
f["event"] = f.ticker.str.rsplit("-", n=1).str[0]
t = None
f["t"] = pd.to_datetime(f.time, utc=True).dt.as_unit("ns").astype("int64")
def phase(r):
    w = W.loc[r.event] if r.event in W.index else None
    if w is None: return "nomatch"
    if r.t < w.espn_start: return "pre"
    if r.t > w.end: return "post"
    for i, (a, b) in enumerate(w.ints):
        if a <= r.t < b: return f"I{i+1}"
    return "live"
f["phase"] = f.apply(phase, axis=1)
f["month"] = f.time.dt.strftime("%Y-%m")
def boot(g, n=1000):
    e = g.groupby("event").agg(net=("net", "sum"), q=("qty", "sum"))
    if len(e) < 5: return (np.nan, np.nan)
    idx = np.random.default_rng(0).integers(0, len(e), (n, len(e)))
    r = 100 * e.net.to_numpy()[idx].sum(1) / e.q.to_numpy()[idx].sum(1)
    return tuple(float(x) for x in np.percentile(r, [2.5, 97.5]).round(2))
def line(name, g):
    q = g.qty.sum(); lo, hi = boot(g)
    print(f"{name:14s} fills {len(g):6d} ctr {q:8.0f} gross {100*g.gross.sum()/q:6.2f}c fee {100*g.fee.sum()/q:5.2f}c net {100*g.net.sum()/q:6.2f}c CI [{lo:6.2f},{hi:6.2f}] games {g.event.nunique()}")
line("POOLED", f)
for k, g in f.groupby("phase"): line("phase " + k, g)
for k, g in f.groupby("month"): line("month " + k, g)
for k, g in f.groupby("side"): line("side " + k, g)
