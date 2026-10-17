# VolFavorite pooled (5 coins)

Markets: KXBTC15M KXETH15M KXSOL15M KXXRP15M KXDOGE15M. derived_from eth-volfav (shares its family/lockbox history).

## Hypothesis (written before testing)
See config.json. Kalshi 15m crypto markets overprice short-horizon vol after volatile stretches; the favourite is cheap
late in the window. Wrong if the walk-forward isn't promising, per-contract edge < ~0.5c in the engine, or lockbox loses.

## Development-data decomposition (research/decomp.py, tab.py, pool*.py; walk-forward HAR per coin, next-trade fills)
- Edge by train-percentile of ratio rises monotonically in every coin (top decile: BTC +1.5, ETH +3.0, SOL +3.3, XRP +1.0,
  DOGE +1.0c with rounded fees); bottom 30% loses 1-3c (the market is right or overpriced-favourite there).
- A model-implied probability (Phi(D/(forecast*sqrt(tau-40)))) is badly calibrated in the tails (predicted +13c, realised
  +0.5c) and a pooled logistic on (z_market, z_forecast) found no OOS edge: rank by ratio percentile, don't price off the forecast.
- Weekend (Sat/Sun UTC close) ~2x weekday at every threshold (q>0.7: +1.86 vs +0.71c, 8/8 months positive). Hour of day:
  noisy, no stable pattern. Price band: nothing stable (>0.95 favourites ~0.9c with unrounded fee). Horizon: 300-360 s best, 180 worst (noise).
- DOGE is the weak coin (3/5 months), XRP decays in Jun-Aug; kept in (pre-register all five).
- Fee note: research fee must be unrounded 0.07P(1-P); per-contract ceil makes >90c favourites look 0.8c worse.
- Pre-registered rule: entry bar = per-coin training quantile of ratio, 0.85 weekdays / 0.60 weekends. Research estimate ~+1.2c.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-14 | pooled rule, 5 coins | smoke | ok | needed params/ group-writable (chgrp lab) for the sandbox fit |
| 2 | 10-14 | same | quick (3 d) | passed, -0.41c, 624 markets, CI -3.3..+2.3 | too short to say anything |
| 3 | 10-14 | same | full (job volfav-pool-1014-155317) | RUNNING at agent deadline. Plan is 4 walk-forward months (May-Aug, first fit needs >=800 markets/coin) + 3 lat2x runs; each month run took ~3.5 h of shared CPU (5 coins, every-second timer). May/Jun/Jul runs done by 19:24 UTC; Aug and lat2x still running. | check results.json / `kalshi-lab wait` for the verdict |

## Current status
- Stage: full test in flight (1 of 3 full budget used). Next: read the verdict; if promising run the lockbox (Sep 1+, one run); if inconclusive, look at per-coin/per-month cards (decompose.py on the run dirs) before changing anything -- candidate motivated change: drop coins whose own cards are negative (DOGE was weakest in research).
- Speed note: a 5-coin full costs ~4 h wall at current load. Consider restricting to ETH/SOL/XRP/BTC or sampling if rerunning.
