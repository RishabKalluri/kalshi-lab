"""Per-decile taker PnL at the next real fill (after fees) for buying YES and buying NO, vs an unconditional
baseline. Tells whether a signal carries information at all (even if not enough to beat costs), and its sign."""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

SERIES = sys.argv[1] if len(sys.argv) > 1 else "KXSOL15M"
COIN = sys.argv[2] if len(sys.argv) > 2 else "eth"
d = pd.read_parquet(Path(__file__).parent / f"screen_{SERIES}_{COIN}.parquet")
d = d[d.mid.between(0.1, 0.9) & d.next_ask.notna() & d.next_bid.notna()].copy()
fee = lambda p: 0.07 * p * (1 - p)
d["pb"] = (d.y - d.next_ask - fee(d.next_ask)) * 100
d["ps"] = ((1 - d.y) - (1 - d.next_bid) - fee(d.next_bid)) * 100
print(f"{SERIES}/{COIN}: n={len(d)}, baseline buy YES {d.pb.mean():+.2f}c, buy NO {d.ps.mean():+.2f}c")
for f in ["bin_imb30", "bin_imb60", "bin_imb300", "bin_sv60", "own_ret30", "own_ret300"]:
    q = pd.qcut(d[f].rank(method="first"), 10, labels=False)
    g = d.groupby(q)[["pb", "ps"]].mean().round(2)
    print(f"\n{f}: decile -> buyYES / buyNO  (c/contract)")
    print("  " + "  ".join(f"{i}:{r.pb:+.1f}/{r.ps:+.1f}" for i, r in g.iterrows()))
