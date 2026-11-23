# nba-q4-state (research only, agent run 20261022-1936-4)

## Hypothesis
Kalshi KXNBAGAME prices at late-Q4 stoppages don't fully use the game state (lead, seconds left, possession, pace, pregame spread). A
gradient-boosted state model trained on ESPN play-by-play (seasons 2017-2024) should find 2c+ mispricings after the taker fee.
Wrong if realized c/contract on held-out games has a CI including 0.

## Data
- PBP: sportsdataverse `espn_nba_pbp` releases 2017-2026 (wallclock timestamps, pregame spread). Kalshi: KXNBAGAME trade prints 2025-10-10 -> 2026-10-13
  (no books). Spread/total series: not in history (KXNBATOTAL is a 150-market sample). Wallclock vs Kalshi price: jump lands ~+3 s after the play's wallclock, done by +12 s.
- Liquidity at the Q3->Q4 break: median 24k contracts in the last 2 min, ~1c ask-bid proxy, 3-minute wallclock break.

## What was done (scripts in research/, data in the run folder)
1. States at end of Q3 and at 480/300/180/120/60 s left in Q4 for every game (12.8k games). Quotes from trade prints; fill = next opposing-taker print within 60 s after play wallclock + 10 s; fee 0.07 p (1-p).
2. Model: HistGradientBoosting on ESPN seasons 2017-2024 only (2024-25 used for PBP-only checks). Frozen. Pre-registration: research/PREREG_nba.md (sha in PREREG_nba.sha256), written before Jan-Jun 2026 quotes were scored.
3. Rule R (T in 300/180/120/60, edge >= 2c): dev Oct-Dec 2025 +7.21c (468 trades, 237 games, CI +1.7..+12.3); **test Jan-Jun 2026 +4.82c (670 trades, 322 games, CI +0.6..+8.7)**, 4 of 4 months with >100 trades positive.
   Same rule priced from the away market's prints: dev +5.7c, test +4.0c (CI +0.2..+8.2). Q3 break (T=720) and 480 s: dev -1.9/+2.5, test +2.7/+3.8 (CIs include 0).
4. Quote-time sensitivity (dev): +7.2c at +10 s, +5.3c at +30 s, +3.0c at +60 s, +0.2c at +120 s with the same stale state (edge needs fast data).
5. Log loss: Kalshi mid beats the model at every T (e.g. Q3 break 0.328 vs 0.335 test) but the model adds information in the disagreement tails (res ~ 0.3-0.5 x (model - mid)).

## Caveats
- Q4-only choice came from dev data (T=720/480 dev were not positive). Fills are trade-print proxies; no historical books. Sizes are untested beyond ~first-print size (median 50 contracts).
- Dollar scale: 120 trades/month; 50-200 contracts per trade gives ~$1.3-3.5k over the 5.5 test months.
- The engine pipeline can't run it (needs live PBP; lockbox runs have no network). No lockbox run was made. Forward test: 2026-27 season games from Oct 21 are the only unseen data.

## Update: possession MC and concentration (same run)
- research/mcsim.py: possession-level Monte Carlo (2.5M parsed possessions, 2017-2024). Better PBP-only log loss than the GBM; standalone taker dev +4.2c / test +1.2c (CIs incl. 0); blend with the Kalshi mid (rule C, weights fit on dev) dev +6.0c, test second look +3.95c (CI -1.4..+8.8), and beats the Kalshi mid on test log loss at every T.
- Concentration: dropping the 10 best games leaves +2.6c (dev) / +1.8c (test) for rule R.

## Engine pipeline (run 20261022-1936-4)
- strategy.py reads signals.csv (GBM p at Q4 T=300/180/120/60, usable from play wallclock+10 s), triggers on a taker print inside 30 s, IOC at the proven ask/bid, edge >= 20 mills after fee. Smoke/quick windows are off-season (Aug 29-Sep 1): no trades, not evidence.
- Full 1/3 (Oct 2025-Aug 2026, overlaps the research dev+test data, so not independent): **reject**. Pooled +2.97c/ct (CI +0.17..+5.97, 699 mkts, 43.7k contracts, 93/188 days), months: Oct -0.7, Nov +7.3, Dec +7.0, Jan +6.8, Feb -2.3, Mar -5.0, Apr -0.1, May -3.1, Jun +9.1 (5 mkts). 4/9 positive < 60%. Unweighted per fill: Nov-Jan +6..+7c, Feb-May -0.5..-2.6c.
- Research print-replay (first opposing print, flat) showed Feb +3.5, Mar +0.8, Apr +7.9 for the same signals: the engine's latency/IOC at a triggering print is less favourable, so the research number was optimistic. Treat the +4.8c as an upper bound; the realistic edge is about +3c, with an unexplained regime change after January.

- Full 2/3 (edge>=40 mills): inconclusive, +3.18c/ct (CI +0.03..+6.65, 581 mkts, 88/180 days); months Oct -3.0, Nov +7.9, Dec +9.0, Jan +4.1, Feb -3.3, Mar -2.3, Apr +1.5, May +6.1, Jun +2.2. Status parked.
