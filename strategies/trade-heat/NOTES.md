# trade-heat (agent run 20261016-0045-1): five dev-data screens, all dead

Data: research/data/KX{BTC,ETH,SOL,XRP,DOGE}15M.parquet (dev dates only), net = outcome - next real fill - unrounded fee 0.07p(1-p).
Halves: A = Dec-Apr, B = May-Aug. Scripts in research/s1..s4.py.

| # | Hypothesis | Result |
|---|---|---|
| s1 | Retail rush: favourite (75-97c, h 240-600) is cheaper when the market's trade count so far is high | flat: quintiles -0.28..+0.23c, se ~0.17, no pattern, no split-half stability |
| s2a | Chop: favourite after the mid crossed 50c (flips) is overpriced | flips>=1 worse than 0 flips in both halves (0 flips +0.66/+0.26c; >=1 flips -0.3..-0.6c; 3 flips B -3.2c), but the underdog side after flips still loses -0.5..-3c (spread + fee), so only usable as a filter, not an edge |
| s2b | Previous window's upset (outcome vs its h=60 mid) predicts the next window | sign flips between halves; noise |
| s3 | Hour-so-far move reverses in the :30/:45 windows | A: y-mid +4.6c (lowest z quintile) to -3.0c (highest); B: +0.2..-0.6c. Decayed like every other reversal effect; below taker cost in B |
| s4 | Weekend favourite bias (no vol model) on 5 coins | 90-95c +0.53c, 95-99c +0.36c weekend (vs +0.36/+0.18 weekday); positive in most months but ~0.5c x 13-contract depth is dollars a month |

Learnings: Kalshi-internal features (activity, path, previous outcome) carry nothing the price lacks. Every
reversal-type effect shows strong Dec-Apr and ~0 May-Aug. Underdogs lose 2-3c at the next fill in every bucket.
