# Favourite bias taker (sol-favbias)

Markets: KXSOL15M (same rule screened on BTC/ETH/DOGE/XRP: same sign).

## Hypothesis (written before any test)
- Why mispriced: underdog buyers overpay for tails (dog-seller: 2-4c), so the 90-95c favourite is slightly cheap. At the
  next real fill, h 300-720 s, SOL: 5,889 markets, win 94.0% vs avg price 92.8% (+0.45c fee): net +0.68c (se 0.31), 7/8 months
  positive. Other coins net: BTC +0.33, ETH +0.58, DOGE +0.57, XRP +0.10 (research/data, dev dates only).
- Who is on the other side: retail underdog takers.
- Wrong if: walk-forward pooled CI <= 0, <60% months positive, negative at 2x latency; the decay Jan-Apr +1.0c -> May-Aug +0.4c
  suggests it may be going to zero. Edge is small: the engine's fill realism (book depth, touch) may remove it.
- Rule fixed in advance: first second with 300 <= seconds_left <= 720 where the touch price of YES or NO is in (90c, 95c];
  buy IOC at the touch; one per market; hold.

## Ideas and prior work used
- sol-gbm/research (GBM: no residual edge; deep favourite buckets in `fav_scan` below), vol-burst H5 (80-97c favourites negative
  on ETH/SOL/BTC: different horizons/buckets), dog-seller (underdog overpayment).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-14 | v1 | smoke | ok (job sol-favbias-1014-010108) | mechanics fine |
| 2 | 10-14 | v1 | quick | passed (gate) but negative: -2.04c/ct, CI -7.2..+2.5, 156 markets, 1577 contracts, t -0.83 | One price-bucket loss (a 90-95c favourite losing costs ~92c) dominates a short window; consistent with a ~0.5c edge being unobservable at this size. Not escalated: capacity 13 contracts (~$1-2/day) and decaying edge make a full test poor value. |

## Learnings

## Current status
- Stage: quick done (-2.0c, noise-level, CI spans 0); parked. SOL book_depth is 13 contracts: capacity ~$1-2/day, so only worth a full test if quick is clearly positive; full 1/3 unused.
