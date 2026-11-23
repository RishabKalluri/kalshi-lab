# Sports extremes maker, trades-source (sports-tails-bf)

Markets: KXNBAGAME, KXNHLGAME. derived_from sports-tails (strategy.py copied unchanged). Agent run 20261106-0059-1.

## Hypothesis (written before any test)
- Why mispriced: takers buying cheap longshots / selling near-certain favourites pay the 1c tick (5-10% of the price there); the maker fee at the extremes is ~0.14c. Same carry as sports-tails.
- Other side: casual in-game/pre-game takers; adverse selection is comebacks (fat left tail: worst 1% of games = 85% of sports-tails' profit).
- Wrong if: pooled walk-forward CI <= 0, 2x latency loses, or the lockbox loses.
- Why a new folder: sports-tails (books source, Jan-Jun) was +1.37c (CI +0.36..+2.36, 1,801 mkts) but sits at 3/3 full tests with the gate unpassable (empty summer months, lat2x only on them). The trades-only backfill source covers Oct 2025-Sep 2026, including the Oct-Dec 2025 game months the books source lacks, so lat2x lands on months with games. Cost: a rougher fill model (synthetic book from the last taker sell/buy, depth 50).
- Pre-registered screen (trade prints, game-clustered, maker-fill proxy, net of 0.0175 p(1-p)): Oct-2025 +1.1c (se 1.3), Nov +1.0 (0.9), Dec +0.8 (0.9); Jan +2.1, Feb +2.5, Mar +1.7 (same proxy). Resting bids at exactly 90c lose (-3c).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|

## Learnings

## Current status
- Stage: ad hoc debugging on Oct-Dec 2025.
