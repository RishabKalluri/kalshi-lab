"""Cross-series consistency at one settlement time. KXBTCD (above/below), KXBTC (ranges) and KXBTC15M
(if it closes then) all settle on the same 60s BRTI average. Price each KXBTC range from the KXBTCD
ladder and flag ranges whose own quotes are outside the ladder-implied bounds after fees."""

import sys
from collections import defaultdict

from kalshi_lab.rest import KalshiREST

c = KalshiREST()
d = lambda x: float(x) if x not in (None, "") else None
close = sys.argv[1] if len(sys.argv) > 1 else None
above = defaultdict(list)
for m in c.markets(series_ticker="KXBTCD", status="open"):
    above[m["close_time"]].append(m)
close = close or sorted(above)[0]
lad = sorted(((m["floor_strike"], d(m["yes_bid_dollars"]), d(m["yes_ask_dollars"]), d(m.get("yes_bid_size_fp")),
               d(m.get("yes_ask_size_fp")), m["ticker"]) for m in above[close] if m.get("floor_strike")), key=lambda x: x[0])
# P(X > k): bid/ask bounds from the ladder
P = {k: (b, a) for k, b, a, *_ in lad}
ranges = [m for m in c.markets(series_ticker="KXBTC", status="open") if m["close_time"] == close]
fee = lambda p: 0.07 * p * (1 - p)
print(f"settlement {close}: {len(lad)} above/below strikes, {len(ranges)} range markets")
live = [x for x in lad if x[1] and x[2] and 0.02 < (x[1] + x[2]) / 2 < 0.98]
print("liquid part of ladder (strike, bid, ask):", [(round(k), b, a) for k, b, a, *_ in live][:12])
opps = []
for m in ranges:
    lo, hi = m.get("floor_strike"), m.get("cap_strike")
    rb, ra = d(m["yes_bid_dollars"]), d(m["yes_ask_dollars"])
    if m.get("strike_type") != "between" or lo is None or hi is None:
        continue
    klo, khi = round(lo - 0.01, 2), round(hi, 2)  # range [lo, hi] == above(lo - 0.01) and not above(hi)
    if klo not in P or khi not in P:
        continue
    (blo, alo), (bhi, ahi) = P[klo], P[khi]
    if None in (blo, alo, bhi, ahi):
        continue
    # range YES == above(lo) YES + above(hi) NO. Synthetic ask = ask(lo) + (1 - bid(hi)) - 1; synthetic bid = bid(lo) - ask(hi)
    syn_ask, syn_bid = alo - bhi, blo - ahi
    if ra is not None and ra + fee(ra) + fee(alo) + fee(1 - bhi) < syn_bid:
        opps.append(("buy range, sell synthetic", m["ticker"], ra, syn_bid))
    if rb is not None and rb - fee(rb) - fee(alo) - fee(1 - bhi) > syn_ask:
        opps.append(("sell range, buy synthetic", m["ticker"], rb, syn_ask))
    if rb and ra and 0.02 < (rb + ra) / 2 < 0.98:
        print(f"  range [{lo:,.0f},{hi:,.0f}): quotes {rb:.2f}/{ra:.2f}   ladder-implied {max(syn_bid,0):.2f}/{syn_ask:.2f}")
print("\ncross-series arbitrages after fees:", opps or "none")
