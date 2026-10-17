# Weather Maker

Markets: KXHIGHNY, KXHIGHLAX, KXHIGHMIA, KXHIGHCHI, KXHIGHAUS

## Hypothesis (written before any test)
- Why the market should be mispriced:
- Who is on the other side, and why they keep losing:
- What result would prove this wrong:

## Ideas and prior work used
- (Other strategies' NOTES.md / results.json, research scripts, external sources you drew on.)

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|

## Learnings
- (Durable lessons, positive and negative, for future strategies to read.)

## Current status
- Stage:
- Next step:

## Hypothesis
Takers lose 0.3-1.6c/ct on weather (cheap brackets worst) and prices are about right vs forecasts, so the spread is the money. Counterparty: retail takers paying 2-3c spreads. Wrong if markouts after fills (adverse selection from forecast/obs updates) exceed the half-spread captured, or if CI of PnL per city-day clusters includes 0.

## Iteration log
- v1: join touch both sides, mid 5-50c, cutoff 13h local, pull 30 mills/10min, cd_cap 400, qty 10. smoke queued 2026-10-15.
- v1 quick: -0.22c/ct CI [-3.7,3.8] (39 markets, Aug 29-31). Smoke cannot work for weather (no live market in its window).
- Ad hoc v1, two-week slices Mar10-24? (actually runs Mar/Apr/May 10-24, Jun 1-7, Jun/Jul 10-24), per-side: bids (buy YES) -2.7c/ct (Mar-Jun1) and -3.6c/ct (Jun10-Jul24, unseen when the hypothesis was formed); asks (sell YES) +1.0c/ct and +1.4c/ct. Bands noisy. Reading: YES is overpriced on brackets (one of ~6 wins), takers paying 20-40c lose; our bids get hit by sellers who know more, our asks are paid the longshot premium.
- v2 = sides=ask (same everything else). Chosen from the side asymmetry seen in two disjoint sets; full walk-forward decides.
- Ad hoc v1 (both sides, 5 cities, two-week slices Mar/Apr/May 10-24, Jun 1-7, Jun/Jul 10-24; Jan/Feb/Aug slices unfinished or lost to an output-dir name collision): bids -2.7c/ct then -3.6c/ct (disjoint sets), asks +1.0 / +1.4c/ct; per-band numbers jump around (+-5c).
- Infra learnings: smoke cannot pass for weather (no live market in the last 6h before 00:00 UTC lockbox start; use --skip-smoke). Config `params` are NOT applied by `kalshi-lab test`, pass `-p`. 5-city full runs died with no error: a 2-city month needs 3.2 GB RSS and the sandbox allows 6 GB for 3 parallel runs, so full tests were run on NY only. My folder wasn't group-writable, so the worker's "PermissionError" lost the v2 result from results.json (fixed with chmod g+ws).
- v2 full (NY only, `-p sides=ask`, join the touch, mid 5-50c): REJECT. pooled -0.32c/ct, CI [-3.4,+2.8], 923 markets, 8 development months (Jan..Aug: +74, -61, -195, +218, -106, -130, -51, +30 dollars). Recorded only in the job output (results.json write failed). By band: 20-40c +0.5c, 10-20c -0.8c, 40-50c -1.6c (favourites get run over).
- v3 full (NY only, ask-only, 2c behind the touch, mid 20-50c; chosen because touch fills are adversely selected): INCONCLUSIVE. +0.88c/ct, CI [-4.4,+6.3], 475 markets, 4/8 months positive (Jan-Mar, May negative; Apr +210, Jul +186, Aug +215 dollars), lat2x +4.2c/ct. Not promising; no lockbox.
## Verdict
Passive weather quoting earns about zero net of adverse selection with the touch-joining rules tried; the longshot premium on asks is real in some months but too small and noisy (city-day pnl SE ~$1.5 per city-day vs mean ~$-0.7..+0.4). Parked; not sent to the lockbox.
