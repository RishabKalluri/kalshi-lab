# EUR/USD bracket fair value (eur-bracket)
Agent run 20261017-2200-3. Brief: financial markets. See that run's report.md H13.

## Hypothesis (before any pipeline run)
See config.json. Screen: first trade per market with |lognormal model - price| > 10c: +35.7c net, 61 of the 150 sampled markets, t~5, all 8 months positive.

## Ad hoc engine check (dev data, Jan 13 - Aug 17, before the pipeline)
edge=100 mills (pre-registered): 8 markets traded, 125 contracts, +39.5c/contract, t=1.06. edge=60: 13 markets, +46.3c, t=1.56. The engine only trades when a trade proves the quote and the spread is <=40c, so it takes 8-13 of the 61 research signals.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|

## Status
developing. Data limit: KXEURUSD is a 150-market sample, not in MARKETS, no spot in the backfill (Yahoo hourly opens in data/).
