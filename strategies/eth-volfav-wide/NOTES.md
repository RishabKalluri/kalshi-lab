# ETH VolFavorite wide (top 40%)

Markets: KXETH15M. eth-volfav2's code with one change: the fitted entry threshold is the 60th percentile of
implied/forecast vol (top 40% of check times) instead of the 70th (top 30%). Asked by the user: can the bar be looser?

## Hypothesis (written before any test)
eth-volfav2 enters only on the top 30% of implied/forecast vol ratios (+2.2c/ct walk-forward). Signals in the next band (30-40%) are weaker but, if ETH's market overprices vol broadly, still worth more than the ~1.3c taker fee; lowering the bar to the top 40% should then add total dollars even as c/contract falls. Wrong if total PnL over the walk-forward is not higher than eth-volfav2's, or the added band's own trades are flat or negative after fees.

## How to judge it
Same walk-forward months as eth-volfav (refit monthly). Compare against eth-volfav2's walk-forward (+2.16c/ct pooled):
total PnL, c/contract, months positive, and the trades in the added band (ratio between the 60th and 70th percentile).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|

## Current status
- Stage: developing (full test queued Oct 14).
