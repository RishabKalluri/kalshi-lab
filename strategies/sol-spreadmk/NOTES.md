# SOL early-window spread maker
Agent run 20261020-0058-2. Brief: KXSOL15M, own idea.

## Hypothesis
Trade-table screen (12.9M SOL prints, Jan-Aug): the counterparty of taker prints at 15-85c earns +0.6c/ct gross (+1.2c in the first 5 min, positive 7/8 months). Makers pay no fee.
Wrong if the engine, which fills us on every trade-through, shows <= 0.

## Log
| # | change | stage | result |
|---|---|---|---|
| 1 | join bid and ask, 5-300 s after open, mid 30-70c, spread >=2c, ttl 20 s, hold to settle | ad hoc Jul 1-7 | -1.84c/ct, 47,170 ct, 638 mkts, t -2.28 |

## Learnings
Same as volfav-maker, dog-seller, btc-maker: the average-print screen flatters makers; trade-through fills are adverse. No pipeline run spent. Needs real books (Nov 1).
| 2 | + spot calm filter (|move over 10 s| <= 1bp), same window | ad hoc Jul 1-7 | -3.16c/ct, 16,964 ct (filtering made it worse) |
| 3 | calm filter + spread >= 3c | ad hoc Jul 1-7 | -3.91c/ct, 10,122 ct |
Taker edge by UTC hour, weekday and side (`sol-perp/research/hrtaker.py`): -1..-2.8c net in every cell of both halves; nothing to select.
Side/time split of run 1 (fills.csv vs result): buy side -1.50c/ct (23,056 ct), sell side -2.16c/ct (24,115 ct); every time bucket 600-900 s left is -0.5..-2.9c. No pocket to keep.
| 4 | favourite-side bid only (mid of favourite 70-90c, spread >=1c, 5 s after open to 60 s before close, ttl 30 s): mid-price calibration says favourites +1..3c under-priced Jun-Aug (`sol-perp/research/mid.py`) | ad hoc Jul 1-14 | -1.16c/ct, 44,618 ct, 1,279 mkts, t -1.16 |
| 5 | same, Aug 1-14 | ad hoc | +0.26c/ct, 81,929 ct, 1,280 mkts, t 0.26. Two samples pool to about -0.3c: no edge. Favourite-longshot bias at mid (+1..3c) is eaten by adverse selection. Rejected, no pipeline run. |
| 6 | favourite-side bid (as rows 4-5), smoke ok, quick | quick | passed (gate only): -1.04c/ct, CI -4.81..+2.73, 288 mkts, 2/4 days |
| 7 | same | full 1/3 | queued (job in report) |
