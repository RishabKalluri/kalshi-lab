# SOL aligned-flow reversal (sol-flowrev)
Agent run 20261018-0059-2. derived_from sol-volrev (family eth-overreact / sol-midrev).

## Hypothesis (before the pipeline)
See config.json. Screen scripts: research/ (copied from /tmp). Rule fixed in advance: sol-volrev's rule with the relv filter replaced by
imb_thr=0.25 on the previous window's Binance taker imbalance aligned with the move.

## Iteration log
| # | date | change | stage | result | learning |
| 1 | 10-18 | v1 | smoke | no fills in the 6 h window (no signal); ad hoc 08-20..31: 56 mkts -2.2c (noise) | --skip-smoke |
| 2 | 10-18 | v1 | quick | passed +9.8c, 15 mkts (noise) | |
