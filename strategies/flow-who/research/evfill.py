"""Shock events (shock2 pickles) -> next real Kalshi taker fill (>=1 s after the event, within 10 s) on the coin's own market,
held to settlement, after fee. Follow = buy the direction of the shock. Streams market by market. Dev only.
    uv run python strategies/flow-who/research/evfill.py ETH"""
import sys, json, math, os, numpy as np, pandas as pd
from pathlib import Path
from kalshi_lab.data.normalize import iso_ns
from kalshi_lab.recorder.sink import EXT, read_lines
from kalshi_lab.validate import LOCKBOX_START
coin = sys.argv[1].upper(); ser = f"KX{coin}15M"
BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
CUT = LOCKBOX_START.strftime("%Y-%m-%d"); LB = pd.Timestamp(LOCKBOX_START).timestamp()
ev = pd.read_pickle(f"/tmp/shock2_{coin.lower()}.pkl").sort_values("t").reset_index(drop=True)
evt = ev.t.to_numpy(); fee = lambda p: math.ceil(0.07 * p * (1 - p) * 100 - 1e-9) / 100
out = []
for day in sorted(p for p in (BF / "kalshi" / ser).iterdir() if p.is_dir()):
    if day.name >= CUT: continue
    for f in sorted(day.glob(f"*{EXT}")):
        L = [json.loads(l) for l in read_lines(f)]
        if L[-1]["m"].get("event") != "settled": continue
        m = L[-1]["m"]["market"]
        if not m.get("result"): continue
        o, c = iso_ns(m["open_time"]) // 10**9, iso_ns(m["close_time"]) // 10**9
        if c >= LB: continue
        lo, hi = np.searchsorted(evt, o), np.searchsorted(evt, c - 90)
        if lo >= hi: continue
        y = int(m["result"] == "yes")
        tr = [(d["t"] / 1e9, float(d["m"]["msg"]["yes_price_dollars"]), d["m"]["msg"]["taker_side"]) for d in L if d["m"].get("type") == "trade"]
        for r in ev.iloc[lo:hi].itertuples():
            t = r.t
            nb = next((p for tt, p, sd in tr if t + 1 <= tt <= t + 11 and sd == "yes"), None)
            ns = next((p for tt, p, sd in tr if t + 1 <= tt <= t + 11 and sd == "no"), None)
            if nb is None or ns is None: continue
            mid = (nb + ns) / 2
            if not 0.1 <= mid <= 0.9: continue
            up = r.s > 0
            fol = (y - nb - fee(nb)) if up else ((1 - y) - (1 - ns) - fee(ns))
            fad = ((1 - y) - (1 - ns) - fee(ns)) if up else (y - nb - fee(nb))
            out.append(dict(t=t, ym=pd.Timestamp(t, unit="s").strftime("%Y-%m"), big=r.big, imb=r.imb, share=r.share, lead=r.lead,
                            avg=r.avg, vr=r.vr, z=r.z, fol=fol, fad=fad, mid=mid))
d = pd.DataFrame(out); d.to_pickle(f"/tmp/evfill_{coin}.pkl")
print(coin, "events", len(ev), "with both-side fills", len(d), f"(~{len(d)/9:.0f}/month)  follow {100*d.fol.mean():+.2f}c  fade {100*d.fad.mean():+.2f}c")
for f in ["lead", "big", "imb", "share", "avg", "vr", "z"]:
    d["q"] = pd.qcut(d[f].rank(method="first"), 3, labels=False)
    print(f"{f:6s} follow c by tercile:", " ".join(f"{100*d[d.q==i].fol.mean():+.2f}" for i in range(3)), "| n/tercile", len(d) // 3)
