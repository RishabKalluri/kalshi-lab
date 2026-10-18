# Crypto hourly ladder fair value (crypto-ladder)
Agent run 20261017-2200-3. derived_from eur-bracket, rule unchanged (edge 100 mills). Ad hoc: KXBTCD 41 mkts +10.2c/ct t=0.97; KXETHD 36 mkts +9.2c t=0.83.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-17 | edge=100 | quick | passed, 1 market | few trades |
| 2 | 10-17 | same | full 1/3 | **inconclusive**: +7.84c/ct, CI -6.69..+23.30, 69 mkts, 1,045 contracts, 25/57 days, max drawdown $40 | Same sign as the ad hoc run (+10c) but 69 trades cannot show a CI above 0. Parked until the full ladders are downloaded. |

## Status
parked.

## Robustness (ad hoc, no selection)
BTCD: edge60 +9.4c, edge150 -4.4c, vol48 -5.1c, vol240 +8.1c, max_ttc6 +10.0c. ETHD: edge60 +7.0c, edge150 +14.1c, vol48 -2.8c, vol240 +10.9c, max_ttc6 +9.5c. 32-49 mkts, |t|<=1.24: sign not stable.
