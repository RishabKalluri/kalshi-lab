# Rain NO wide window (rain-no-wide)
Agent run 20261017-2200-3. derived_from rain-no (strategy.py is rain-no's with window 6-30 h before close, bid 10-75c).

## Hypothesis (before any test)
See config.json. Fixed-time screen on KXRAIN dev data (Jul 16 - Aug 31, 845 markets, `rain.py` in the run folder): first trade after h<=18: YES price 0.1-0.25 realized 0.10 (-7c, se 3), 0.25-0.5 realized 0.255 (-12c, se 6), 0.5-0.75 realized 0.43 (-21c, se 6.5); at h<=30 -2.7/-5.6/-18.6c. Trades only, so the tradable version (hit the bid after a taker sell) pays the half spread.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-17 | rain-no rule, 6-30 h window, bid 10-75c, taker-sell trigger | quick (Aug 29-31) | passed, +0.36c, 21 mkts, CI -19.8..+20.9 | noise (3 days) |
| 2 | 10-17 | same | full 1/3 | **promising**: +7.88c/ct, CI +3.26..+12.41, 409 mkts, 7,394 contracts, 30/41 days, Jul +18.8c (CI 8.4..28.4), Aug +4.5c (CI -0.7..+9.4); 2x latency identical (synthetic backfill book); max drawdown $77.5 | Two earlier jobs (full 220516, quick 220456) computed the same numbers but weren't recorded: the worker couldn't write into this folder (mode 755, no group write), fixed with chmod g+w and rerun |

## Status
developing.
