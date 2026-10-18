# Mention sell-YES (mention-sell)

derived_from mention-no (parked, data-blocked). Agent run 20261017-2158-1. Rule: taker SELL trade proves the YES bid; if bid in 10-90c and the market's first
trade was <=3 h ago, buy NO at the bid (IOC), one per market, hold.

## Hypothesis (before the pipeline)
Opening YES prices on "will Trump say X" are ~14c too high (36% of words said vs ~50c). Wrong if the walk-forward CI <= 0.

## Iteration log
| # | change | stage | result |
|---|--------|-------|--------|
| 1 | v1 | ad hoc Jan 10-Aug 1 | 60 mkts, +20c/ct (t 2.24) |
| 2 | v1 | quick (3 days) | passed, 1 market |
| 3 | v1 | full 1/3 (Jan-Aug sample) | **inconclusive** +13.3c/ct, CI -1.62..+28.3, 69 markets, 27/47 days positive, 525 contracts |

## Status
parked: sample-limited (150 markets, 86 events; history ends Aug 17, so no lockbox data). The point estimate is large (+13c) but 69 markets cannot
exclude zero. Needs the full KXTRUMPMENTION history (and its MARKETS config) to get hundreds of trades and a Sep-Oct lockbox. Full tests used 1/3.

## v2 (max_age_h 1.0) -- chosen from the mention-no screen (mispricing decays with age: h0 +6.5c, h1 +3.7c, h3 +3.0c), after v1's inconclusive +13.3c
| 4 | v2 | full 2/3 | **promising** +23.35c/ct, CI +3.78..+40.82, 37 markets, 324 contracts, 18/30 days positive, max DD $15 |

Caveats: only 37 markets (one-per-market entries on a 150-market sample), v2 was chosen after seeing v1 on the same sample, no lockbox data exists (history ends
Aug 17) so the lockbox stage cannot be run honestly. Not a paper candidate. Needs the full KXTRUMPMENTION history + MARKETS config; then rerun full and lockbox.
Real books at listing may be wide or absent: the proven-bid synthetic book is optimistic. Full tests used 2/3.
