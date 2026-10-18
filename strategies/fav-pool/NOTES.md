# Favourite bias on SOL+XRP+DOGE (fav-pool)
Agent run 20261018-0059-2. derived_from sol-favbias (rule unchanged; sol-favbias is parked: SOL only, quick -2.0c on 156 mkts, full unused).

## Hypothesis (before the pipeline)
See config.json. Screen (research/fav.py, rec.py; dataset next-fill prices, one trade per market): the 90-95c favourite at h 300-720 nets +0.73c/ct in Jun-Aug on
five coins pooled (n=15.1k), every coin positive; and the (0,10] / (10,40] c tails lose 2-3c at h 300-600, i.e. the favourite-longshot bias, intact in the recent era.

## Iteration log
| # | date | change | stage | result | learning |
| 1 | 10-18 | v1 | smoke | ok | |
| 2 | 10-18 | v1 | quick | passed, -1.71c/ct CI -4.5..+0.9, 441 mkts, 3 days (a handful of 92c losses dominate a 3-day window) | proceed to full |
