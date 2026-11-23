# VolFavorite night hours (volfav-night)

Agent run 20261025-0057-2 (brief KXSOL15M, pivoted after SOL taker screens died). derived_from volfav-pool.

## Hypothesis (written before any test of this folder)
See config.json. volfav-pool's rule, only for windows closing 00:00-11:59 UTC, on ETH+SOL+XRP+DOGE (BTC dropped: efficient).
- Who loses: thin-hours retail takers who pay for vol after a swing that does not recur.
- Evidence (dev only, markets.csv of finished full tests, by UTC close hour): night vs day c/ct DOGE +1.9 vs -0.9, XRP +2.0 vs +0.7, ETH +2.4 vs +0.5 (12-17 block -0.8), SOL +1.9 vs +1.9 (no split), volfav-pool +2.2 vs +0.7. Four-coin pool: night +2.07c (6,577 mkts), day +0.57c (6,409); months May-Aug night>day 4/4.
- Disclosure: the cut was found by looking at those dev results, volfav-pool's own research said "hour-of-day shows no stable pattern" (pooled over all coins with different thresholds). A clean test is the lockbox only.
- Wrong if: see config.json.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-25 | v1: volfav-pool rule, ETH/SOL/XRP/DOGE, 00-11 UTC closes | smoke ok; quick passed (4 days, 227 mkts, -1.38c, CI -6.2..+3.2, noise); full 1/3 job volfav-night-1025-011038 in flight at session end | read results.json for the verdict | |

## Current status
- Stage: full 1/3 in flight. Next: if promising, one lockbox run; else record per-month/per-coin/per-hour breakdown here.

## Lockbox pickup (run 20261027-0057-1)
Full 1/3 was promising (+2.61c, CI +1.61..+3.58, 3,986 mkts), so queued the one lockbox run (job volfav-night-1027-010420, code unchanged) at 01:04 UTC Oct 27. Still running 6 h later at the agent's deadline (4 coins); read the verdict in results.json. Weak evidence by design: the night cut was found on dev results and the parent volfav-pool failed its lockbox (-1.08c).
