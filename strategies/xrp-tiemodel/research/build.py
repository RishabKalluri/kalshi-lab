"""Build XRP 15m market table + per-second Binance spot arrays (dev dates only). Output: research/data/*.pkl"""
import sys, json, os, glob, pickle, datetime as dt
import numpy as np, zstandard as zstd
LOCK = "2026-09-01"
B = "/srv/kalshi-data/backfill"
out = "/srv/kalshi/strategies/xrp-tiemodel/research/data"; os.makedirs(out, exist_ok=True)
def lines(p):
    with open(p, "rb") as f:
        data = zstd.ZstdDecompressor().stream_reader(f).read()
    return data.decode().splitlines()
days = sorted(d for d in os.listdir(f"{B}/kalshi/KXXRP15M") if d < LOCK and d[:2] == "20")
rows = []
for d in days:
    for p in sorted(glob.glob(f"{B}/kalshi/KXXRP15M/{d}/*.jsonl.zst")):
        K = ev = None; res = None; close = None; tr = []
        for ln in lines(p):
            j = json.loads(ln); m = j["m"]
            if m.get("event") == "discovered":
                K = m["market"].get("floor_strike", K)
                close = dt.datetime.fromisoformat(m["market"]["close_time"].replace("Z", "+00:00")).timestamp()
            elif m.get("event") == "settled":
                mk = m["market"]; K = mk.get("floor_strike", K); ev = mk["expiration_value"]; res = mk["result"]
            elif m.get("type") == "trade":
                g = m["msg"]
                tr.append((j["t"] / 1e9, float(g["yes_price_dollars"]), 1 if g["taker_side"] == "yes" else -1, float(g["count_fp"])))
        if K is None or close is None or not ev: continue
        tr = [x for x in tr if x[0] >= close - 120]
        rows.append(dict(ticker=os.path.basename(p)[:-9], close=close, K=K, ev=float(ev), res=res, tr=tr))
print(len(rows))
spot = {}
for d in days:
    p = f"{B}/spot/binance_xrpusdt/{d}.jsonl.zst"
    if not os.path.exists(p): continue
    a = np.full(86400, np.nan)
    t0 = dt.datetime.fromisoformat(d).replace(tzinfo=dt.timezone.utc).timestamp()
    for ln in lines(p):
        j = json.loads(ln); i = int(j["t"] / 1e9 - t0)
        if 0 <= i < 86400: a[i] = j["m"]["price"]
    spot[d] = a
pickle.dump(rows, open(f"{out}/markets.pkl", "wb")); pickle.dump(spot, open(f"{out}/spot.pkl", "wb"))
