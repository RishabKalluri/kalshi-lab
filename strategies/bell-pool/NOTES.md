# Scheduled Bell Pool (bell-pool)

Markets: KXETH15M, KXBTC15M (fixed in advance; SOL excluded). derived_from us-hours-vol (shares its lockbox: unused so far).

## Hypothesis (written before any test)
- Scheduled TradFi venue openings are vol steps that Kalshi's 15-minute prices (trailing-vol based) underprice:
  the 9:30 ET US equity open on NYSE trading days (us-hours-vol: +1.03 log vol vs month mean; implied vol ~0.3 log low;
  weekend/holiday placebo flat) and the Sunday 18:00 ET CME reopen (cme-reopen: +0.9 log on ETH/BTC; gap 0.0 vs 0.25).
  The underdog is cheap in both. Each alone is ~1 market per coin per day / week: us-hours-vol's full 2/3 had 237
  markets (+4.3c, CI -1.5..+10.5); cme-reopen adds ~1/week/coin.
- Other side: favourite buyers and bots pricing off trailing vol without a clock prior.
- Wrong if: pooled full walk-forward CI not > 0, < 60% of months positive, or the Sunday bell drags the pool.

## Pre-registration (before any pipeline run)
- Rule = us-hours-vol v2 (checkpoints 600/480/360/300/240 s, underdog 10-45c, spread <= 6c, IOC at touch, hold) over
  windows {NYSE-day 09:30 ET, Sunday 18:00 ET}. Nothing tuned on this data.
- Coins ETH+BTC. SOL excluded (post-hoc, from research): its 9:30 and Sunday underdog are -0.5c / +0.7c (prices both bells).
  BTC kept: +7.0c at 9:30 (both halves positive); Sunday BTC -3.7c (n=21) is noise-level, kept because the rule is
  one rule across bells.
- Mon-Thu 18:00 (daily CME reopen) screened and excluded: ETH +5.1c (se 4.5), BTC -0.7c, SOL -4.5c; neighbouring
  slots no better. Not a bell.

## Opportunities (research/pool.py, dev data, first qualifying checkpoint per market, next real fill, after fee)
| | n | mean c | se | A / B |
|---|---|---|---|---|
| ETH 9:30 | 119 | +10.9 | 4.2 | +16.5 / +5.9 |
| ETH Sun 18:00 | 16 | +9.8 | 12.4 | -5.6 / +21.7 |
| BTC 9:30 | 140 | +7.0 | 3.9 | +5.7 / +8.6 |
| BTC Sun 18:00 | 21 | -3.7 | 9.9 | -0.6 / -6.4 |
| **ETH+BTC pooled** | **296** | **+8.0** | **2.7** | +8.8 / +7.1, 8 of 9 months positive |
(+SOL: 418 markets, +5.6c.) About 35 markets/month; ~300 over development. The engine got about half of research's
figure for the 9:30 bell (+4.3c), so expect ~+4c, se ~3: a CI above 0 is possible but not certain. The Sunday bell adds
only ~37 markets (13%), so the gain over us-hours-vol is modest; honest expectation is "inconclusive, maybe promising".

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|

## Learnings
## Current status
- Stage: smoke.
