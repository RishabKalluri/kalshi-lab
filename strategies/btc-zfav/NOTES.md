# Spot-confirmed favourite (btc-zfav)
Agent run 20261029-0058-2. derived_from sol-favbias (favourite bias), but conditioned on spot distance in sigmas.

## Hypothesis (before testing)
Favourites priced ~92c at 8-10 min left win ~95% when spot is already >2 sigma (rv15*sqrt(tau)) past the strike.
Research (BTC, taker next fills net of fee, Dec-Aug): tau 600 |z|>2 +2.57c (se 0.70, 924 trades, 8/9 months positive);
tau 480 +1.3c (2,174); ETH similar (+0.4..+2.5c), SOL/XRP/DOGE too rare or flipping. Opportunities ~100/month BTC.
Wrong if engine fills or depth remove it, months not >=60% positive, 2x latency negative.

## Iteration log
| # | change | stage | result |
|---|---|---|---|
| 1 | v1 z>=2, tau 600/540/480, BTC+ETH, max price 97c | smoke ok; quick passed -4.4c (CI -14..+4, 51 mkts, noise) | |
| 2 | same | full 1/3 (job btc-zfav-1029-010806) | running 4.5 h+ at the agent's deadline (queue shared); read results.json |
| 3 | same code (picked up by run 20261030-0057-1) | full 1/3 result | promising +2.16c (CI +1.43..+2.87, 3,595 mkts, 8/9 months positive, lat2x +2.01c) |
| 4 | same code | lockbox (one run) | job btc-zfav-1030-005801 still running after 6 h at the agent deadline; read results.json |
