# KXHIGH cheap-bracket offers, AUS/LAX/DAL (wx-cheap-ask-b)
Agent run 20261024-0057-1. derived_from wx-cheap-ask: the **rule is unchanged** (sides=ask, mid 20-100 mills, spread>=10, cutoff 13:00 local,
wx-maker code), only the cities differ (Austin, Los Angeles, Dallas; the parent ran NY/CHI/MIA). Only change in strategy.py: the TZ table gets
the other KXHIGH cities (no behaviour change for the parent's cities). Note: the parent's cheap band came from a trade-print grid that included
these cities, so this is a replication on new markets, not a fully clean out-of-sample test.

## Hypothesis
Retail YES buyers of cheap daily-high brackets overpay ~1-2c at every low band; a resting offer collects it with no maker fee.
Parent: dev +1.00c (CI +0.09..+1.93, 8/8 months), lockbox +0.64c (CI -1.84..+2.84). Wrong if pooled full CI <= 0 or <60% of months positive.

## Iteration log
| # | change | stage | result |
|---|--------|-------|--------|
