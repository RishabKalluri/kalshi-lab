# XRP tie-goes-YES (xrp-tie)

Agent run 20261017-2158-1. Found by running the series x price x ttc x side screen on the crypto 15M series (research: strategies/resrule-screen/research/c15.py logic).

## Mechanism
Rule: YES if the 60 s average at the close is AT LEAST the 60 s average at the open. XRP's strike and expiration_value are rounded to 4 decimals (ETH/SOL/BTC/DOGE
have 2-6+ decimals on bigger/smaller price scales: no ties). With ties going YES, the final minute is a discrete distribution; the market prices it as continuous.
Dev screen (all taker trades, 200 days): last minute YES takers +5..+14c (10-60c), NO takers -16..-24c, both halves; by seconds-left: (0,2] +35c, (2,5] +45c,
(5,10] +30c, (10,20] +30c, (20,30] +19c, (30,45] +6.6c, (45,60] +1.9c (73-86% win at 10-70c).

## Big caveat (written before the pipeline)
Those late buyers are probably informed (they see the spot average) and the winners are what the screen counts. Following them at the same price assumes the
ask they paid is still there 150 ms later; the backfill book is synthesized from the last trade (optimistic). The only check is the recorded XRP books
(Oct 13-17, inside the lockbox). Treat any backtest number as an upper bound.

## Hypothesis
Wrong if the walk-forward CI <= 0, 2x latency loses, or the lockbox (47 days, 4 with real books) loses.

## Iteration log
| # | change | stage | result |
|---|--------|-------|--------|
| 1 | v1 max_s 60, min_s 3, ask 10-70c | ad hoc June | 43 mkts, +2.6c |
| 2 | max_s 30 (screen: edge concentrated in the last 30 s), min_s 3 | ad hoc June | 86 mkts, +9.2c, t 1.65 |
