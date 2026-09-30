"""Is the late-window gold edge real or a stale-quote artifact?

Signal (fit on the first half of dates): logistic blend of market mid and the OKX spot model.
Fills scored three ways on the second half:
  stale  - the last taker price on that side (what model_edge.py used)
  fresh  - only signals whose last same-side trade is < 10s old
  next   - the next same-side taker trade within 10s after the signal (what we'd actually pay)
"""

import json
import os
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize
from scipy.stats import norm
from sklearn.linear_model import LogisticRegression

from kalshi_lab.data.normalize import iso_ns
from kalshi_lab.recorder.sink import EXT, read_lines

BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
H = [300, 240, 180, 120, 60]
THR = 0.03

px = {}
for f in sorted((BF / "spot" / "okx_xauusdtswap_1m").glob(f"*{EXT}")):
    for line in read_lines(f):
        d = json.loads(line)
        px[d["t"] // 10**9] = d["m"]["price"]
secs = np.array(sorted(px))
vals = np.array([px[s] for s in secs])


def S(t):  # last minute close at or before t
    i = np.searchsorted(secs, t, side="right") - 1
    return vals[i] if i >= 0 else np.nan


def rv60(t):
    i = np.searchsorted(secs, t, side="right") - 1
    w = vals[max(0, i - 60): i + 1]
    return float(np.sqrt(np.mean(np.diff(w) ** 2) / 60)) if len(w) > 10 else np.nan


rows = []
for f in sorted((BF / "kalshi" / "KXGOLD15M").glob(f"*/*{EXT}")):
    lines = [json.loads(l) for l in read_lines(f)]
    m = lines[-1]["m"].get("market", {})
    if m.get("floor_strike") is None or not m.get("result"):
        continue
    o, c = iso_ns(m["open_time"]) // 10**9, iso_ns(m["close_time"]) // 10**9
    K = m["floor_strike"]
    base = S(o)
    if np.isnan(base):
        continue
    tr = [(d["t"] / 1e9, float(d["m"]["msg"]["yes_price_dollars"]), d["m"]["msg"]["taker_side"])
          for d in lines if d["m"].get("type") == "trade"]
    tt = np.array([x[0] for x in tr])
    for h in H:
        t = c - h
        i = np.searchsorted(tt, t, side="right")
        past = tr[:i]
        lb = next(((x[0], x[1]) for x in reversed(past) if x[2] == "yes"), None)
        ls = next(((x[0], x[1]) for x in reversed(past) if x[2] == "no"), None)
        if not lb or not ls:
            continue
        fut = tr[i:]
        nb = next((x[1] for x in fut if x[2] == "yes" and x[0] <= t + 10), None)
        ns = next((x[1] for x in fut if x[2] == "no" and x[0] <= t + 10), None)
        rows.append(dict(ticker=m["ticker"], close=c, h=h, y=int(m["result"] == "yes"), D=S(t) - base + (K - K),
                         rv=rv60(t), ask=lb[1], bid=ls[1], age_a=t - lb[0], age_b=t - ls[0], next_ask=nb, next_bid=ns))
df = pd.DataFrame(rows).dropna(subset=["rv"])
df = df[df.rv > 0]
df["mid"] = ((df.ask + df.bid) / 2).clip(0.005, 0.995)
df["day"] = pd.to_datetime(df.close, unit="s").dt.date
split = df.close.quantile(0.5)
train, test = df[df.close < split], df[df.close >= split]
brier = lambda p, y: float(np.mean((p - y) ** 2))
z = lambda d, k, b: d.D / np.sqrt(k**2 * d.rv**2 * d.h + b**2)
res = minimize(lambda x: brier(norm.cdf(z(train, abs(x[0]), abs(x[1]))), train.y), [1.0, 0.5], method="Nelder-Mead")
k, b = abs(res.x[0]), abs(res.x[1])
X = lambda d: np.column_stack([norm.ppf(d.mid), z(d, k, b).clip(-8, 8)])
fee = lambda p: 0.07 * p * (1 - p)

def report():
    out = []
    for h in H:
        lr = LogisticRegression(C=10).fit(X(train[train.h == h]), train[train.h == h].y)
        for name, d in (("train", train[train.h == h]), ("test", test[test.h == h])):
            p = lr.predict_proba(X(d))[:, 1]
            for side in ("buy", "sell"):
                sig = (p - d.ask > THR) if side == "buy" else (d.bid - p > THR)
                s = d[sig].copy()
                if side == "buy":
                    s["stale"] = s.y - s.ask - fee(s.ask)
                    s["fresh_ok"] = s.age_a < 10
                    s["next"] = np.where(s.next_ask.notna(), s.y - s.next_ask - fee(s.next_ask.fillna(0.5)), np.nan)
                else:
                    s["stale"] = s.bid - s.y - fee(1 - s.bid)
                    s["fresh_ok"] = s.age_b < 10
                    s["next"] = np.where(s.next_bid.notna(), s.next_bid - s.y - fee(1 - s.next_bid.fillna(0.5)), np.nan)
                s["half"], s["side"] = name, side
                out.append(s)
    o = pd.concat(out)
    print(f"gold: vol mult {k:.2f}, basis noise ${b:.2f}; signals at |blend - quote| > {THR}\n")
    for half in ("train", "test"):
        d = o[o.half == half]
        fr = d[d.fresh_ok]
        nx = d.dropna(subset=["next"])
        print(f"{half:>5}: stale {d.stale.mean()*100:+6.2f}c (n={len(d)})   fresh-only {fr.stale.mean()*100:+6.2f}c (n={len(fr)})"
              f"   next-trade fill {nx['next'].mean()*100:+6.2f}c (n={len(nx)}, {len(nx)/max(1,len(d)):.0%} of signals fillable)")
    t = o[(o.half == "test")].dropna(subset=["next"])
    g = t.groupby("ticker")["next"].sum()
    boot = [g.sample(frac=1, replace=True).sum() / t.groupby("ticker").size().reindex(g.index).sum() for _ in range(2000)]
    print(f"\ntest, next-trade fills: 95% CI by market bootstrap: [{np.percentile(boot, 2.5)*100:+.2f}c, {np.percentile(boot, 97.5)*100:+.2f}c]")
    byday = t.groupby("day")["next"].sum()
    print(f"test days positive: {(byday > 0).sum()}/{len(byday)}")
    print("\nby horizon (test, next-trade fills):")
    print(t.groupby("h")["next"].agg(["mean", "size"]).assign(mean=lambda x: (x["mean"] * 100).round(2)).T.to_string())

    # --- session split: is the edge concentrated in US hours (08:00-17:00 New York)?
    o["et_hour"] = pd.to_datetime(o.close, unit="s", utc=True).dt.tz_convert("America/New_York").dt.hour
    o["session"] = np.where(o.et_hour.between(8, 16), "US 8-17 ET", "overnight")
    print("\nnext-trade-fill PnL by session (cents/contract, n):")
    for (half, sess), g in o.dropna(subset=["next"]).groupby(["half", "session"]):
        print(f"  {half:>5} {sess:<11} {g['next'].mean()*100:+6.2f}c  n={len(g)}  markets={g.ticker.nunique()}")



if __name__ == "__main__":
    report()
