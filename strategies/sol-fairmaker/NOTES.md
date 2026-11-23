# SOL fair-value protected maker (sol-fairmaker)
Agent run 20261105-0059-2. derived_from sol-zfav-maker (same maker idea, signal generalised from |z|>=1.5 to a continuous fair value).

## Hypothesis (before testing)
Why: SOL liquidity grew 5-8x since June, spreads are ~0.7c, and the taker side is dead (round 10/11 screens). sol-zfav-maker (strong lockbox pass +1.34c) shows that a post-only quote on the right side of a spot-confirmed move earns the spread plus a favourite premium. Quoting off a spot-vol fair value on every z, with a margin (mills) between quote and fair value, tests whether the maker edge is only a favourite effect or general.
Who loses: takers hitting a stale resting quote after the spot has moved; holders selling to our bid for liquidity reasons.
Wrong if: PnL/contract <= 0 at margins of 1-5c on development windows (earlier makers lost 0.5-2c to adverse selection), or the fill rate disappears at margins that remove the adverse selection.
Prior: ~15%. Opportunities: every market (~96/day), one fill per market held to settlement; thousands of markets over development months.

## Log
| # | change | stage | result |
|---|---|---|---|
| 1 | margin 20 mills (2c), tau 600..120, ttl 15, p in 10..90c | ad hoc Sep 1-8 | -0.005 $/ct (-0.5c), 630 mkts, 9,280 ct, t -0.23 |
