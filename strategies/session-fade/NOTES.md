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
