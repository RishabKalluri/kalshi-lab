# SOL zfav maker, drift-only filter (sol-zfav-drift)
Agent run 20261106-0100-2. derived_from sol-zfav-maker: same family and lockbox evidence.

## Hypothesis
See config.json. Jump-dominated displacement (largest 10 s move > 45% of the move since open) is already priced / adversely selected; drift-like displacement leaves the favourite underpriced.

## Research (research/screen1-3.py, dev fills of sol-zfav-maker walk-forward Jan-Sep, 6,614 fills)
- screen1: BTC/ETH move with SOL (market-wide) vs SOL alone: no pattern (quintiles +0.7/+1.2/+0.8/+1.9/+1.3c). Dead.
- screen2: Binance/OKX taker imbalance 60/300 s and intensity at fill: non-monotone noise. Dead.
- screen3: jump share of displacement: <=0.45 +1.85c (3,922, se 0.30), >0.45 +0.07c (2,594, se 0.43); low side positive 8/9 months. Used as the filter.
- Ad hoc (also from this run): sol-zfav-early with zmin 1.0/1.25/1.5 on Aug 1-15: +1.58/+0.18/+0.98c, non-monotone noise, lowering zmin dead.
- Ad hoc engine run Sep 1-15 of this strategy: +2.27c (4,003 ct) vs parent +1.23c (Sep is inside the screen, so not independent).

## Log
| # | change | stage | result |
|---|---|---|---|
| 1 | v1 filter 0.45 | smoke ok; quick passed (noise) -1.42c, CI -6.6..+3.0, 108 mkts | |
