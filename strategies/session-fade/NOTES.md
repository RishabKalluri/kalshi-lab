# Session Fade at 16:00 ET, BTC+ETH+SOL (folder session-fade)

Markets: KXBTC15M, KXETH15M, KXSOL15M. Derived from `strategies/btc-flowrev/` (H3), rule **unchanged**.

## Hypothesis (fixed before any test of this folder)
- btc-flowrev H3: from 09:30 to 16:00 ET the US session's flow (spot-ETF creations into the 15:00-16:00 ET CF fixing,
  CME settlement and the equity close at 16:00) pushes crypto with the session; at 16:00 it stops and part reverts.
  Kalshi's 16:00 ET window opens near 50/50.
- Why a new folder: BTC alone gives ~1 market a day; its full walk-forward was inconclusive (+7.27¢/ct, CI −2.5..+16.1,
  5/9 months, 113 markets). Spot research showed the same reversal on ETH (corr −0.34/−0.38) and SOL (−0.27/−0.46), so
  the unchanged rule on all three markets roughly triples the sample (same-day trades are correlated, so less than 3×).
- No parameter changes: |R| > 0.5, h = 870/840/810/780, mid 30–70¢, touch IOC, NYSE full trading days only.
- Wrong if: the full walk-forward isn't promising, or the lockbox loses.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|

## Current status
- Stage: developing, not yet tested. Smoke can't trade (its 6 h window starts after 09:30 ET; no spot warm-up in
  backtests): verify with an ad-hoc dev run, then quick and full with `--skip-smoke`. A full test replays three series
  per month (btc-midrev's took ~10 h on battery): run it on power.

## Run log (agent run 20261014-0055-1)
| # | stage | result | learning |
|---|-------|--------|----------|
| 1 | smoke | failed: no fills (expected: window starts after 09:30 ET, no warm-up) | mechanics only |
| 2 | quick | rejected: 8 markets, -30c, CI -50.6..-2.5 | n=8 is noise; gate still let full queue |
| 3 | full | promising: +8.04c/ct, CI +1.95..+13.66, 274 mkts, 84/128 days, 6/8 months (Apr -3.7, Aug -6.5; Jun +33.8 dominates), 2x latency +10.6c (CI +0.3..+20.6) | Edge uneven; last month negative |
| 4 | lockbox | job ran, then CRASHED reading results/_lockbox/.../summary.json (PermissionError). No ledger entry; result unseen. | infra bug, report to user |

Status: parked pending the lockbox readout. Budget: 1/3 full, lockbox shot probably consumed.

## Lockbox (2026-10-14, recorded by the main session)
First run crashed (a deploy changed file ownership under it; no verdict recorded). Rerun session-fade-1014-lockbox3 on the rolling lockbox (from 2026-09-01): **fail**, -12.0c/contract, 95% CI -24.3..+0.3, 58 markets, 11/26 days positive. Rejected: the full-test edge (+8.0c, CI +1.9..+13.7) did not hold on unseen data.
