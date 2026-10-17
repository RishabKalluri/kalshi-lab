"""Weather ladder consistency: for each city-day, on a 60 s grid, sum of best YES asks / best YES bids over all
brackets of the event (they are mutually exclusive and exhaustive, so sum of fair values = 1). Screening only."""
import sys, json, glob, os
from pathlib import Path
import numpy as np, zstandard
ROOT = Path("/srv/kalshi-data/backfill/books")
def series_of(path):
    book = {"yes": {}, "no": {}}; ts, bb, ba, bbq, baq = [], [], [], [], []
    for line in zstandard.ZstdDecompressor().decompress(path.read_bytes(), max_output_size=2**32).splitlines():
        d = json.loads(line); m = d["m"]; msg = m.get("msg", {})
        if m["type"] == "orderbook_snapshot":
            book = {"yes": {k: float(v) for k, v in (msg.get("yes_dollars_fp") or [])},
                    "no": {k: float(v) for k, v in (msg.get("no_dollars_fp") or [])}}
        elif m["type"] == "orderbook_delta":
            lv = book[msg["side"]]; q = lv.get(msg["price_dollars"], 0.0) + float(msg["delta_fp"])
            if q > 1e-9: lv[msg["price_dollars"]] = q
            else: lv.pop(msg["price_dollars"], None)
        else: continue
        yb = max(book["yes"], key=float) if book["yes"] else None
        nb = max(book["no"], key=float) if book["no"] else None
        ts.append(d["t"]); bb.append(float(yb) if yb else np.nan); ba.append(1 - float(nb) if nb else np.nan)
        bbq.append(book["yes"][yb] if yb else 0); baq.append(book["no"][nb] if nb else 0)
    return np.array(ts), np.array(bb), np.array(ba), np.array(bbq), np.array(baq)
def grid(ts, v, g):
    j = np.searchsorted(ts, g, side="right") - 1
    return np.where(j >= 0, v[np.maximum(j, 0)], np.nan)
ser = sys.argv[1]; days = sys.argv[2:]
for day in days:
    ev = {}
    for f in sorted((ROOT / ser / day).glob("*.jsonl.zst")):
        ev.setdefault(f.name.rsplit("-", 1)[0], []).append(f)
    for e, fs in ev.items():
        data = [d for d in (series_of(f) for f in fs) if len(d[0])]
        if len(data) < 3: continue
        t0 = max(d[0][0] for d in data); t1 = min(d[0][-1] for d in data)
        g = np.arange(t0, t1, 60 * 10**9)
        if len(g) < 100: continue
        B = np.array([grid(d[0], d[1], g) for d in data]); A = np.array([grid(d[0], d[2], g) for d in data])
        Bq = np.array([grid(d[0], d[3], g) for d in data]); Aq = np.array([grid(d[0], d[4], g) for d in data])
        ok = ~np.isnan(A).any(0) & ~np.isnan(B).any(0)
        if ok.sum() < 30: continue
        sa, sb = A.sum(0)[ok], B.sum(0)[ok]
        minq_a = Aq.min(0)[ok]; minq_b = Bq.min(0)[ok]
        print(e, len(fs), "mkts", ok.sum(), "min", "| ask-sum min %.3f med %.3f (n<0.99: %d, with qty>=10: %d) | bid-sum max %.3f med %.3f (n>1.01: %d, qty>=10: %d)" % (
            sa.min(), np.median(sa), (sa < .99).sum(), ((sa < .99) & (minq_a >= 10)).sum(), sb.max(), np.median(sb), (sb > 1.01).sum(), ((sb > 1.01) & (minq_b >= 10)).sum()), flush=True)
