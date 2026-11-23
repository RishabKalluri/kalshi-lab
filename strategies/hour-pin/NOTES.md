# hour-pin: hour-end late favourite (BTC+ETH+XRP)

Agent run 20261028-0057-1. Found in a screen of the research datasets (research/slot.py, slot2.py, hourpin.py; dev data only, close < 2026-09-01).

## Hypothesis (written before any pipeline run)
Windows that close on the hour (:00 UTC) have calmer final minutes than windows that open on the hour: future realized vol (h=300) vs trailing 60 min is
~15 log-points lower for hour-closing windows on all five coins, in both Dec-May and Jun-Aug; Kalshi's implied vol prices only about half of it.
So the favourite (85-98c) in the last 1-4 minutes of an hour-closing window wins more often than its price. Rule: one entry per market at the first of
tau = 240/180/120/60 s where the favourite's ask is in 850-980 mills, hold to settlement; windows closing at :15/:30/:45 are not traded.
Who loses: takers buying the cheap underdog in a calm final stretch. Wrong if the full CI includes 0, <60% of months positive, 2x latency loses, or the lockbox loses.

## Evidence (dev screen, next-fill prices after fees, one entry per market)
| close slot | n | edge c/ct | months+ |
|---|---|---|---|
| :00 (hour-closing) | 16,637 | +0.74 (se 0.18; day-clustered +0.87 se 0.24) | 7/9 |
| :15 | 16,344 | -1.61 | 1/9 |
| :30 | 16,074 | -0.46 | 2/9 |
| :45 | 16,005 | -0.07 | 4/9 |
Slot :00 by coin: BTC +1.01, ETH +1.25, XRP +1.01, SOL +0.43, DOGE -0.42; by month Jan -0.8, Feb +0.8, Mar +1.6, Apr +0.7, May +1.3, Jun +1.2, Jul +0.4, Aug -0.1, Dec +3.1.
Disclosure: the :00 slot and the coin set (BTC/ETH/XRP; SOL and DOGE dropped) were chosen after seeing these dev numbers; the edge is also fading in Jul-Aug.
A quarter-hour dummy in the HAR vol forecast adds only +0.0..+0.2c to VolFavorite-style selection, so this is a different (late-favourite) effect.
Caveats: dev fills are next-trade prints, the engine's backfill book is synthetic (last-trade based); real-book lockbox days differ. The edge is ~1c: any extra cost kills it.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-28 | v1 as above | smoke | ok | agent folders need chgrp -R lab + g+rwX + setgid params/ before the worker can write |
| 2 | 10-28 | v1 | quick (4 days) | passed: 153 mkts, -2.90c (CI -8.2..+1.9), noise | |
| 3 | 10-28 | v1 | full 1/3 | queued | |

## Current status
- Stage: full 1/3 queued. Next: if promising, the one lockbox run; otherwise record per-month and per-coin cards here.

## End of agent run 20261028-0057-1
Full 1/3 (job hour-pin-1028-011138) still running at the agent's deadline (>5 h, shared worker). Not read. Next: read results.json; lockbox only if promising (one run, code unchanged). Expectation: dev edge +0.7c and fading (Jul +0.4, Aug -0.1), so a lockbox pass would be weak evidence.

## Agent run 20261029-0057-1
Read full 1/3: promising. Pooled +0.666c (CI +0.192..+1.167), 8,528 mkts, all 7 months positive (Feb +0.31, Mar +1.01, Apr +0.84, May +1.02, Jun +0.25, Jul +0.78, Aug +0.24); POOLED-lat2x +0.325c (CI -0.51..+1.18). Queued the one lockbox run, code unchanged (job hour-pin-1029-005813); still running at the deadline. Read results.json.
