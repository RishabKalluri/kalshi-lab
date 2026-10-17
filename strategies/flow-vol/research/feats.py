"""Order-flow features at each dataset row's decision time (close - h), development data only.
usage: feats.py KXETH15M   -> strategies/flow-vol/research/feats_<SERIES>.parquet
Flow row t covers (t-1, t]; a decision at second T uses rows t <= T-1 (no lookahead)."""
import sys
from datetime import date, timedelta
from pathlib import Path
import numpy as np, pandas as pd
from kalshi_lab.data.flow import flow_sources, FLOW

LOCK = date(2026, 8, 20)
series = sys.argv[1]
src = flow_sources(series)
d = pd.read_parquet(f"research/data/{series}.parquet")
d = d[d.close < "2026-08-20"].copy()
T = d.close.values.astype("datetime64[s]").astype(np.int64) - d.h.to_numpy()
T0 = int(T.min()) - 20000 - (int(T.min()) - 20000) % 86400
T1 = int(T.max()) + 1
N = T1 - T0 + 1


def dense(source):
    cols = {k: np.zeros(N) for k in ["buy", "sell", "n", "mx"]}
    day = date.fromtimestamp(T0) if False else pd.Timestamp(T0, unit="s").date()
    while pd.Timestamp(day).value // 10**9 < T1 and day < LOCK:
        p = FLOW / source / f"{day.isoformat()}.parquet"
        if p.exists():
            f = pd.read_parquet(p)
            i = f.t.to_numpy() - T0
            ok = (i >= 0) & (i < N)
            i = i[ok]
            cols["buy"][i] = f.buy.to_numpy()[ok]; cols["sell"][i] = f.sell.to_numpy()[ok]
            cols["n"][i] = f.n.to_numpy()[ok]
            if "max_trade" in f and f.max_trade.notna().any():
                cols["mx"][i] = f.max_trade.fillna(0).to_numpy()[ok]
        day += timedelta(days=1)
    return cols


bn, ok = dense(src["binance"]), dense(src["okx"])
cs = lambda a: np.concatenate([[0.0], np.cumsum(a)])
C = {f"{ex}_{k}": cs(v) for ex, c in [("bn", bn), ("ok", ok)] for k, v in c.items() if k != "mx"}
vol = {"bn": bn["buy"] + bn["sell"], "ok": ok["buy"] + ok["sell"]}
# rolling max trade (okx) over 60 / 300 s
mx = pd.Series(ok["mx"])
MX = {w: mx.rolling(w, min_periods=1).max().to_numpy() for w in (60, 300)}
mxb = pd.Series(bn["mx"])
i = T - 1 - T0  # last usable index (flow row t=T-1)


def W(key, w):
    a = np.clip(i - w + 1, 0, N); b = np.clip(i + 1, 0, N)
    return C[key][b] - C[key][a]


out = d[["ticker", "close", "h"]].copy()
eps = 1e-9
for w, tag in [(30, "30s"), (60, "1m"), (300, "5m"), (900, "15m"), (3600, "60m"), (14400, "4h")]:
    v_bn = W("bn_buy", w) + W("bn_sell", w); v_ok = W("ok_buy", w) + W("ok_sell", w)
    n_bn = W("bn_n", w); n_ok = W("ok_n", w)
    out[f"lv_{tag}"] = np.log((v_bn + v_ok) / w + eps)            # log volume per second (coin units, both venues)
    out[f"ln_{tag}"] = np.log((n_bn + n_ok) / w + eps)            # log trades per second
    if w in (60, 300, 900):
        out[f"perp_{tag}"] = v_ok / (v_ok + v_bn + eps)           # perp share
        s_bn = W("bn_buy", w) - W("bn_sell", w); s_ok = W("ok_buy", w) - W("ok_sell", w)
        out[f"aimb_{tag}"] = np.abs(s_bn + s_ok) / (v_bn + v_ok + eps)  # |net taker imbalance|
        out[f"simb_{tag}"] = (s_bn + s_ok) / (v_bn + v_ok + eps)
for w in (60, 300):
    out[f"lmx_{w}"] = np.log(MX[w][i] + eps)
out.to_parquet(Path(__file__).parent / f"feats_{series}.parquet")
print(series, len(out), out.isna().mean().max())
