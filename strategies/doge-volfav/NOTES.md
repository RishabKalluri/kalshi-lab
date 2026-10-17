# DOGE VolFavorite

Markets: KXDOGE15M (Kalshi 15-minute DOGE up/down; same 60s-average CF Benchmarks settlement as ETH).

Port of `eth-volfav2` (strategy.py and vol_fit.py copied unchanged; see eth-volfav/NOTES.md for how it works).
Requested by the user to expand VolFavorite to other markets; XRP and DOGE were the best candidates in the Oct 12
expansion survey (volume, history since Feb 11 / Mar 19).

## Hypothesis (written before any test)
ETH's 15-minute market overprices short-horizon vol and the BTC market does not; the difference looks like efficiency (thinner, more retail markets misprice more). DOGE's 15-minute market is smaller and more retail than ETH's, so the same overpricing should appear. The other side: traders paying up for the trailing side late in the window. Wrong if the walk-forward on DOGE is flat or negative, or the edge appears only in one or two months.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|

## Current status
- Stage: developing. Backfill book_depth for KXDOGE15M is a placeholder (13, SOL's) until books are recorded.
