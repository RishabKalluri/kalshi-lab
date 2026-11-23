# KXHIGH late-afternoon favourite carry (wx-late-fav)
Agent run 20261022-0127-1. Markets: 10 KXHIGH city-high ladders (close at local midnight; settle next day).

## Hypothesis (before the pipeline)
Screen (research on trade prices, first trade per ticker per hour bucket, Oct 2025-Aug 2026, fee-adjusted): buying the likely side at 6-10 h before close,
price 80-98c: +1..+3c (se 0.3-1.1c); 4-6 h bucket negative (-1..-12c), so the sign is bucket-dependent and the screen ignores spreads.
Counterparty: retail bracket spreaders. Wrong if walk-forward CI <= 0, <60% months positive, 2x latency negative, or lockbox loses.
Rule: first taker-BUY print (proves the ask) in 6-10 h before close with ask 85-97c, spread <= 3c, IOC buy YES, one per bracket.

## Iteration log
| # | change | stage | result |
|---|--------|-------|--------|
| 1 | v1 | smoke | no fills (window after 6h; expected for weather) |
| 2 | v1 | quick | passed, -11.98c, 16 mkts, noise |
| 3 | v1 | full 1/3 | **reject**: -1.00c/ct, CI -2.60..+0.56, 1,425 mkts, 14,931 ct, 95/200 days, max DD $197 |

## Learnings
- Trade-price screens of "buy the favourite" in KXHIGH overstate by the spread and by adverse selection; at real asks (taker-buy trigger) the carry is slightly negative.

