# Pregame maker (rejected: mid-price quoting loses the maker fee)

Markets: KXNBAGAME, KXNHLGAME (EPL/NFL: too little data, see Learnings).  source: books (Predexon historical order books + Kalshi trades).
The surviving idea that came out of this work lives in `strategies/sports-tails/` (derived_from this folder).

## Hypothesis (written before any test)
- Pre-game takers pay the spread and prices are calibrated (longshot-fade), so a post-only maker joining the touch before
  the game and pulling at tip-off/puck-drop earns the spread with little adverse selection (news arrives slowly).
- Wrong if net-of-maker-fee PnL/contract has CI <= 0. Prior from the numbers: tick 1c, half-spread 0.5c, maker fee
  0.0175*p*(1-p) = 0.44c at 50c, so ~0.06c left at mid prices before adverse selection.
- Game start = expected_expiration_time - 171 min (NBA/NHL: median 168 min, 90% within 162-172), so backtest = paper = live
  without a schedule feed; quotes pulled `pull_min` before.

## Engine caveat (important)
`backtest.py` builds `Fees()` = maker rate 0 for every series, so engine PnL for makers is FEE-FREE. `research/fills_an.py` /
`fills_pool.py` recompute the exact maker fee (ceil(0.0175*q*p*(1-p)) per fill) and cluster-bootstrap by game.
Also: with the pipeline's default 5 s timeline, a month of NBA+NHL books uses ~13 GB (engine._sample over ~100 active markets); ad hoc runs
used `--timeline-s 0`. The pipeline sandbox is limited to 6 GB.

## Research (strategies/pregame-maker/research/)
- Data (an1/an2): NBA pre-game volume is huge (~900k contracts/market, 365k in the last hour), spread is 1c (the tick) with 20-40k contracts at
  the touch at every hour from 1 to 12 h before; 24-72 h before the spread is 5-10c but with ~160 contracts. Taker outcome edge pre-game:
  about 0 in the last 12 h, +5..+25c (noise/informed) 24-72 h before in NBA.
- Markout of v1 fills (markout.py, Feb+Mar, 13.6k fills): +0.36c at 60 s, +0.25c at 300 s vs mid, flat across hours-to-start, price bucket and
  queue imbalance; maker fee 0.41c => about -0.2c.
- Flow (flow_sig.py): trades that go WITH the previous 30 s-10 min of taker flow have markout +0.08c (informed); against: -0.6c.
- EPL (epl.py): backfill has a 150-market sample (121 events), not a season: untestable. NFL: 9 development days.
- Heavy NBA favourites (fav.py): >= 90c at T-15 min win 98.4% vs 92.7% (63 events, 9 of them Jan-Feb, concentrated in Mar-Apr): too rare.

## Iteration log
Ad-hoc engine backtests (books source, back of queue, 150 ms), net = after exact maker fee. No pipeline stage was run for this folder: the
smoke window (Aug 31) has no games (0 orders) and pipeline memory cannot hold sports books (see above).
| # | date | change | window | result | learning |
|---|------|--------|--------|--------|----------|
| 1 | 10-16 | v1 touch maker both sides, 6 h -> 8 min before est. start, band 10-90c | Feb | gross -0.21c, net -0.63c (CI -2.4..+1.0), 94.7k ctr | fee ~ half spread |
| 2 | 10-16 | same | Mar | gross +1.83c, net +1.42c (CI -0.5..+3.3) | outcome noise is +-2c per month |
| 3 | 10-16 | same | Jan 7-Mar 31 pooled | **net -0.09c, CI [-1.04, +0.84]**, 20.0k fills, 266k ctr, 928 games, 1/3 months positive | zero |
| 4 | 10-16 | H2: quote_h=72, min_spread=20, improve=1 tick | Feb | gross +0.01c, net -0.43c; fills 24-80 h before start gross -0.5..-1.2c | early takers are informed; mid of a 10c book is meaningless (markout looked like +1..6c) |
| 5 | 10-16 | H3: pull the side hit by one-sided 2-min taker flow (flow_w=120) | Feb | gross +0.47c (+0.68c vs v1) but fill markout unchanged 0.36/0.22c | improvement was outcome noise |
| 6 | 10-16 | tails=1 (extremes only, in-game) | Jan-Jun | see sports-tails | the one that works |

## Learnings
- At mid prices NBA/NHL game markets are fee-efficient: tick 1c, maker fee ~ half-spread, informed takers earn the rest. A back-of-queue
  maker cannot win there. Only the cheap-fee extremes (p<=10c or >=90c) leave spread after the fee.
- Early (24-80 h) wide spreads are not an opportunity: thin books, informed sharp takers.
- Mid-based markouts are only meaningful when the book is tight; outcome-based PnL per contract has +-2c noise per month on ~300 games,
  so single months mean nothing; pool months and cluster by game.
- Engine fees for makers are zero and the pipeline timeline eats memory (13 GB/month): both need fixing before sports maker strategies
  can go through the pipeline.

## Current status
- Stage: rejected at ad-hoc engine runs (v1, net -0.09c, CI includes 0). No pipeline run. Next: see sports-tails.
