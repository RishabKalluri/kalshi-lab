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
| 1 | 10-13 | port of eth-volfav2 with price-relative fit filter (as xrp-volfav) | fit | betas 0.50/0.18/0.23, threshold 1.22 | |
| 2 | 10-13 | smoke + quick | quick | smoke −33¢/ct (6 mkts); quick −7.4¢/ct (57 mkts, CI −18.7..+3.5) | passed the gate (not clearly negative) |
| 3 | 10-13 | full walk-forward May–Aug 19 | full | **inconclusive**: pooled +0.57¢/ct, CI −0.45..+1.57, 3,157 markets; months +0.72/+1.08/−1.32/+0.21; 2× latency +0.44 | at most a small edge on DOGE; not enough to justify the lockbox. 2 full tests left |

## Current status
- Stage: **parked** (full test inconclusive, +0.57¢/ct). Lockbox for KXDOGE15M untouched.
- Next, if revisited: more history (DOGE has only May–Aug development months) or a DOGE-specific reason to change one thing.
