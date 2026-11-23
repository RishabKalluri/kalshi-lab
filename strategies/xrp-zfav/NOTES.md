# XRP late spot-confirmed favourite (xrp-zfav)
Agent run 20261031-0059-1. derived_from sol-zfav (rule unchanged: zmin 1.5, checkpoints 360/300/240, max ask 97c). Same family/lockbox evidence as btc-zfav / sol-zfav.

## Hypothesis (before testing)
Same as sol-zfav: favourites priced ~95c with spot >= 1.5 sigma past the strike win more often than priced. XRP is thinner than BTC/ETH, so less efficient (cf. xrp-volfav-early).
Screen (research dataset, Feb-Aug dev only, taker next fills net of fee, z=D/S/(rv_15m*sqrt(tau))): tau 360 +2.54c (626 trades, se 0.41, 7/7 months); 300 +1.41c (588, 6/7); 240 +1.56c (388, 6/7). Opportunities ~90-100 trades/month.
DOGE screened with the same rule: -1.0c at all three checkpoints (2/6 months), dropped. Wrong if: engine depth/latency erase it, <60% months positive, 2x latency negative.

## Iteration log
| # | change | stage | result |
|---|---|---|---|
| 1 | v1 | smoke ok; quick passed +2.6c (CI -1.7..+5.6, 71 mkts, 3/3 days) | noise-level sample |
| 2 | v1 | full 1/3 queued | |
| 2 | v1 | **full 1/3: promising** | +1.71c/ct, CI +1.11..+2.29, 3,879 mkts, 41k contracts, 137/202 days, 6/7 months positive (Feb +5.2, Mar +1.4, Apr +2.4, May +0.1, Jun -0.6, Jul +0.9, Aug +2.3); 2x latency +0.89c (CI -0.07..+1.79); DD $88 |
| 3 | v1 | lockbox queued (code unchanged) | |
