"""Add 1s-spot features to the research dataset rows (dev only): bipower/jump share, realized skew, signed jump.
Writes strategies/vol-burst/research/feats_<SERIES>.parquet (gitignored? kept small: only new columns + keys)."""
import json, sys, numpy as np, pandas as pd
from pathlib import Path
from kalshi_lab.recorder.sink import EXT, read_lines
from kalshi_lab.recorder.config import spot_map

series = sys.argv[1]
BF = Path("~/kalshi-data/backfill").expanduser()
src = spot_map([series], backfill=True)[series][0]
secs, px = [], []
for f in sorted((BF / "spot" / src).glob(f"*{EXT}")):
    if f.name[:10] >= "2026-08-20":
        continue
    for line in read_lines(f):
        d = json.loads(line); secs.append(d["t"] // 10**9); px.append(d["m"]["price"])
secs, px = np.array(secs), np.array(px, dtype=float)
T0 = int(secs[0]); spot = np.full(int(secs[-1]) - T0 + 1, np.nan); spot[secs - T0] = px
idx = np.where(~np.isnan(spot), np.arange(len(spot)), 0); np.maximum.accumulate(idx, out=idx); spot = spot[idx]
r = np.concatenate([[0.0], np.diff(np.log(spot))])
c2 = np.cumsum(r ** 2); c3 = np.cumsum(r ** 3); cbp = np.cumsum(np.concatenate([[0.0], np.abs(r[1:]) * np.abs(r[:-1])]))
# 1-minute returns for a microstructure-robust skew
d = pd.read_parquet(f"research/data/{series}.parquet")
d = d[d.close < "2026-08-20"].copy()
t = (d.close.astype("int64") // 10**3 if d.close.dtype.unit == "ms" else d.close.astype("int64") // 10**9).to_numpy()
t = (d.close.values.astype("datetime64[s]").astype(np.int64)) - d.h.to_numpy()
i = t - T0
def W(c, n):
    a = np.clip(i - n, 0, len(c) - 1); b = np.clip(i, 0, len(c) - 1); return c[b] - c[a]
for n, tag in [(900, "15m"), (3600, "60m")]:
    rv = W(c2, n); bp = (np.pi / 2) * W(cbp, n)
    d[f"jump_{tag}"] = np.clip(1 - bp / np.where(rv > 0, rv, np.nan), 0, 1)
    d[f"rskew_{tag}"] = np.sqrt(n) * W(c3, n) / np.where(rv > 0, rv ** 1.5, np.nan)
    d[f"bv_{tag}"] = np.sqrt(bp / n)
# largest 1s abs return in last 15 min, signed
def maxjump(k):
    a, b = max(k - 900, 0), k
    seg = r[a:b]; j = np.argmax(np.abs(seg)); return seg[j]
d["maxj_15m"] = [maxjump(k) for k in i]
d["ret_15m"] = np.log(spot[np.clip(i, 0, len(spot)-1)] / spot[np.clip(i - 900, 0, len(spot)-1)])
d["ret_60m"] = np.log(spot[np.clip(i, 0, len(spot)-1)] / spot[np.clip(i - 3600, 0, len(spot)-1)])
out = Path(__file__).parent / f"feats_{series}.parquet"
d.to_parquet(out); print(out, len(d))
