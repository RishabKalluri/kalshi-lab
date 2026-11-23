# XRP tie model (xrp-tiemodel)

Agent run 20261019-0056-1, derived_from `xrp-tie` (its "untried" idea: a signal from the spot 60 s average instead of copying late buyers).

## Mechanism and research (development data Feb 11 - Aug 31, 18.9k markets)
- Settlement: round4(avg of 60 CF prices) >= K, K rounded the same way => P(YES) = P(avg >= K - 0.5 tick). XRP was $1.1-1.4 in dev, tick = 0.7-0.9 bp.
- Binance XRPUSDT 60 s average vs CF: raw error +4.4 ticks mean, sd 6.5 ticks, but a basis ratio (CF/Binance) from the last 4 strikes
  (the strike of a window = CF average of the minute before its open) leaves sd 1.6 ticks (1.1 bp), normal-ish, widening to ~1.4 bp at 30 s left.
- Unconditional P(YES | est - K, s=5): -3..-1.5 ticks 0.10, -1.5..-0.5 0.32, -0.5..0.5 0.63, 0.5..1.5 0.93, 1.5..3 0.975. Only ~16% of markets (~14/day) have |est-K| < 3 ticks.
- Trade-level (all taker prints, last 3-30 s, |est-K|<3 ticks): buying YES at the printed ask nets +2..+13c by month (Feb +3.9, Mar +2.0, Apr +7.5, May +10.7, Jun +12.9, Jul +10.9, Aug +5.7),
  buying NO -9..-19c every month. Selected by the taker's own side (informed-flow caveat) but the bid-hitting sellers (NO side) lose the same amount, so it is the tie mispricing, not just copying.
- Caveat: backfill books are synthetic (last taker buy = ask); real asks may vanish within 150 ms.

## Strategy
On any trade in the last 3-30 s: estimate P(YES) = Phi((est - (K - 0.5 tick)) / sd(s)), buy YES at the ask when the ask came from a taker buy within 3 s and P - ask - fee >= 4c
(ask 5-97c), once per market. Rule uses only spot and strikes up to now.

## Iteration log
| # | change | stage | result |
|---|--------|-------|--------|
| 1 | v1 edge 4c | ad hoc Jun 1-14 | 43 mkts, +5.5c/ct (xrp-tie same window: 37 mkts, +10.7c) |
| 2 | v1 unchanged | smoke ok, quick passed (12 mkts, -3.5c, noise) | |
| 3 | v1 unchanged | **full 1/3** | **promising** +8.03c/ct, CI +4.63..+11.50, 706 mkts, 11,853 ct, 116/195 days, months Feb +23.3, Mar +13.0, Apr +5.5, May +9.4, Jun +2.2, Jul +8.6, Aug +5.1 (7/7); 2x latency +3.14c (CI -0.83..+7.34, Jun +0.4, Jul +6.0, Aug +2.1) |
