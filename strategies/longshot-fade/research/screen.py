"""Screen: at fixed checks (every STEP s) during the game, buy NO on a market whose last YES trade (within 5 min) is < thr.
Entry price proxy = last price (+SLIP), fee 0.07*p*(1-p). Reports edge/contract clustered by game. Dev data only."""
import sys, json, numpy as np, zstandard, pickle
from pathlib import Path
sys.path.insert(0, "/srv/kalshi/research")
import sports_breaks as sb
sched = json.loads(Path("/srv/kalshi/strategies/longshot-fade/research/schedule.json").read_text())
root = Path("/srv/kalshi-data/backfill/kalshi"); lb = sb.lockbox_start().strftime("%Y-%m-%d")
NS = 10**9; STEP = 60
def pv(t, p, x):
    j = np.searchsorted(t, x, side="right") - 1
    return p[j] if j >= 0 else np.nan

cache = Path("/tmp/lf_checks2.pkl")
if cache.exists():
    rows = pickle.loads(cache.read_bytes())
else:
    rows = []  # (series, event, ticker, sec_in, frac_elapsed, last_yes_price, yes_won)
    for s in ("KXNBAGAME", "KXNHLGAME"):
        for f in sorted(root.glob(f"{s}/*/*.jsonl.zst")):
            if f.parent.name >= lb: continue
            t, p, res, et = [], [], None, None
            for line in zstandard.ZstdDecompressor().decompress(f.read_bytes(), max_output_size=2**31).splitlines():
                r = json.loads(line); m = r["m"]
                if m.get("type") == "trade": t.append(r["t"]); p.append(float(m["msg"]["yes_price_dollars"]))
                elif m.get("event") == "settled": res = m["market"]["result"]; et = m["market"]["event_ticker"]
            if res not in ("yes", "no") or et not in sched or not t: continue
            g = sched[et]; t = np.array(t); p = np.array(p); o = np.argsort(t, kind="stable"); t, p = t[o], p[o]
            for ck in range(g["start"] + 60 * NS, g["end"], STEP * NS):
                j = np.searchsorted(t, ck, side="right") - 1
                if j < 0 or ck - t[j] > 300 * NS: continue
                rows.append((s, et, f.stem, (ck - g["start"]) / NS, (ck - g["start"]) / (g["end"] - g["start"]), p[j], res == "yes", pv(t, p, ck - 180 * NS), pv(t, p, g["start"])))
    cache.write_bytes(pickle.dumps(rows))
print(len(rows), "checks", len({r[1] for r in rows}), "games")
import collections
def stats(sel, label, slip=0.01):
    # fade longshot: buy NO at (1-p)+slip. one position per check; cluster by game
    pg = collections.defaultdict(lambda: [0.0, 0.0])
    for s, et, tk, sec, fr, p, y, *_ in sel:
        cost = 1 - p + slip; fee = 0.07 * cost * (1 - cost)
        pg[et][0] += (0 if y else 1) - cost - fee; pg[et][1] += 1
    a = np.array(list(pg.values())); 
    if len(a) < 5: print(label, "n/a"); return
    rng = np.random.default_rng(0); idx = rng.integers(0, len(a), (1000, len(a)))
    bs = 100 * a[idx][:, :, 0].sum(1) / a[idx][:, :, 1].sum(1)
    print(f"{label:34s} checks {int(a[:,1].sum()):6d} games {len(a):4d} net {100*a[:,0].sum()/a[:,1].sum():6.2f}c CI {np.percentile(bs,2.5):6.2f}..{np.percentile(bs,97.5):6.2f}")
if __name__ == "__main__":
    for s in ("KXNBAGAME", "KXNHLGAME"):
        for lo, hi in ((0.02,0.1),(0.1,0.2),(0.2,0.3),(0.3,0.5)):
            stats([r for r in rows if r[0]==s and lo<=r[5]<hi], f"{s} p {lo}-{hi}")
        for flo, fhi in ((0,.33),(.33,.66),(.66,1.01)):
            stats([r for r in rows if r[0]==s and 0.05<=r[5]<0.25 and flo<=r[4]<fhi], f"{s} p.05-.25 frac {flo}-{fhi:.2f}")
