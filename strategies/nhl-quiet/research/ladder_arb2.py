"""Ladder arbitrage episodes with fees: sell YES on every bracket at the bids (collect sum bids > 1, pay 1) or buy YES on every
bracket at the asks (exhaustive ladder: pays 1). Per 60 s grid, size = min top-of-book quantity (capped), fees = ceil-to-cent taker fee
per leg. Screening only (books; ignores 150 ms legging risk)."""
import sys, json, math
from pathlib import Path
import numpy as np
sys.path.insert(0, ".")
from ladder_arb import series_of, grid, ROOT
CAP = 200
def fee(q, p):  # taker fee, dollars, per order
    return math.ceil(round(0.07 * q * p * (1 - p) * 100, 6)) / 100
ser = sys.argv[1]; days = sys.argv[2:]
tot = {"bid": [], "ask": []}
for day in days:
    ev = {}
    for f in sorted((ROOT / ser / day).glob("*.jsonl.zst")):
        ev.setdefault(f.name.rsplit("-", 1)[0], []).append(f)
    for e, fs in ev.items():
        data = [d for d in (series_of(f) for f in fs) if len(d[0])]
        if len(data) < 3: continue
        t0 = max(d[0][0] for d in data); t1 = min(d[0][-1] for d in data)
        g = np.arange(t0, t1, 60 * 10**9)
        if len(g) < 30: continue
        B = np.array([grid(d[0], d[1], g) for d in data]); A = np.array([grid(d[0], d[2], g) for d in data])
        Bq = np.array([grid(d[0], d[3], g) for d in data]); Aq = np.array([grid(d[0], d[4], g) for d in data])
        n = len(data)
        for kind, P, Q in (("bid", B, Bq), ("ask", A, Aq)):
            okm = ~np.isnan(P).any(0)
            prof = np.zeros(len(g))
            for j in np.where(okm)[0]:
                p = P[:, j]; q = int(min(Q[:, j].min(), CAP))
                if q < 1: continue
                s = p.sum()
                gross = (s - 1) if kind == "bid" else (1 - s)
                if gross <= 0: continue
                fees = sum(fee(q, x if kind == "ask" else 1 - x) for x in p)
                prof[j] = gross * q - fees
            # episodes: consecutive positive minutes -> take max profit within the episode
            pos = prof > 0; i = 0
            while i < len(g):
                if pos[i]:
                    k = i
                    while k < len(g) and pos[k]: k += 1
                    tot[kind].append((e, k - i, prof[i:k].max()))
                    i = k
                else: i += 1
for kind in ("bid", "ask"):
    r = tot[kind]
    print(kind, "episodes", len(r), "sum of best profit per episode $%.0f" % sum(x[2] for x in r), "median len min", np.median([x[1] for x in r]) if r else 0,
          "median $%.2f" % (np.median([x[2] for x in r]) if r else 0), "events", len({x[0] for x in r}))
