# SOL volume-confirmed reversal (sol-volrev)
Agent run 20261017-0101-2. derived_from eth-overreact (z1 reversal at the open; family also sol-midrev).

## Hypothesis (before the pipeline)
Screen (`../macro-bell/research/volrev2.py`, dev data Jan-Aug 2026, SOL, |z1|>1.25 MAD-normalised, next-fill after fee): reversal edge by tercile of the previous
window's Binance volume relative to the same slot's trailing-14-day median: low -0.4/-0.7c, mid +4.3/-1.7c, high +6.1/+3.0c (halves Jan-Apr / May-Aug).
Dose-response at h=840 only: relv>1 +2.9c (n=1449, se 1.2), >2 +4.1c (n=699, se 1.8), >3 +5.7c (n=395, se 2.3). Top tercile positive in 5/7 months.
Opportunities: relv>2 about 700 of ~5,000 reversal-candidate markets in 8 months: ~90/month. Why: heavy-volume big moves are forced flow (liquidations) that unwinds.
Caveat: the threshold came from looking at this screen (post hoc); the walk-forward is out-of-sample only through the engine rule, not the threshold. Paper/live needs live Binance volume (not streamed).
Wrong if: full pooled CI <= 0, 2x-latency loses, lockbox loses.

## Iteration log
| # | date | change | stage | result | learning |
| 1 | 10-17 | v1 z>1.25, relv>2 | smoke | worker PermissionError (my folder lacked group write; chmod g+w fixed it); strategy ran and traded in an ad-hoc dev backtest | |
| 2 | 10-17 | v1 | quick | passed, +11.9c, 3 mkts | noise |
| 3 | 10-17 | v1 | full (Jan-Aug) | **promising** +3.72c/ct, CI +0.41..+6.71, 916 mkts, 12,950 ct, 6/8 months positive (Jan +6.6, Feb +0.6, Mar +12.7, Apr +1.0, May +7.7, Jun -0.1, Jul +11.7, Aug -2.4), 2x latency +1.22c (CI -3.7..+6.4) | full 1/3 used. Same fade-decay shape: Jun/Aug flat or negative. ~115 trades/month. Threshold relv>2 was chosen from the dev screen, so the walk-forward is not out-of-sample for it; the lockbox is the real test |
| 4 | 10-17 | v1 unchanged | **lockbox (Sep 1 - Oct 17)** | **pass (weak)**: +2.77c/ct, CI -5.26..+10.80, 147 mkts, 2,050 ct, +$56.7, 23/38 days positive, max DD $63 | edge shrank vs dev (3.7 -> 2.8c), CI includes 0 |

## Status / learnings
paper_candidate, with caveats: (1) lockbox pass is weak (CI includes 0); (2) relv threshold chosen from the dev screen; (3) trades overlap sol-midrev/eth-overreact (same family: counts as one piece of evidence);
(4) paper/live need a live Binance volume stream (backtest reads backfill flow files); (5) edge fades in Jun/Aug like every z1 reversal.
Learning: the z1 reversal's surviving edge is after heavy-volume moves (forced flow); on ETH/BTC the screen points the same way (not run in the engine).
