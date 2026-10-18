# SOL plain open reversal (sol-overreact; started as a maker-entry experiment)
Agent run 20261018-0059-2. derived_from sol-volrev (signal = previous-window |z|>1.25 on strike-to-strike move, same as eth-overreact).

## Hypothesis (before testing)
See config.json. Execution experiment: same signal as sol-volrev/sol-midrev without the volume filter (more trades), but entry is a
post-only order at our side's touch, cancelled at 600 s left if unfilled. Compare to the IOC taker version on the same dates.

## Iteration log
| # | date | change | stage | result | learning |
| 1 | 10-18 | maker=1 vs maker=0 (post-only at touch / 1 tick inside vs IOC), plain z>1.25, 2-week ad hoc windows | ad hoc | Jun: taker +1.5c vs maker(touch) -2.1c (40/173 orders missed); Jul: taker +0.6, maker(touch) +0.6, maker(+1 tick) +2.5; Feb/Mar/Apr/May/Aug taker +3.9/+6.2/+1.5/+7.4/+7.1 vs maker(+1) +5.1/+3.0/+2.0/+10.0/+7.3 | no separable gain from maker entry (adverse selection offsets fee saved; ~100 trades per window, se ~4c); drop it, use the taker. Side result: the plain z1 rule on SOL nets ~+4c/ct across these windows after fees |
| 2 | 10-18 | v1 taker plain z>1.25, maker=0 | smoke | failed "no fills" (6 h window 08-31 18:00 had no signal); ad hoc 08-30..31 traded 12 mkts | used --skip-smoke |
| 3 | 10-18 | v1 | quick | passed +8.6c, 33 mkts, CI -7.1..+24.6 | noise |
| 4 | 10-18 | v1 | full 1/3 | promising +3.25c/ct, CI +1.33..+5.22, 2,212 mkts, 31,368 ct; months Jan +3.8 Feb +0.8 Mar +8.6 Apr +5.4 May +6.4 Jun -0.6 Jul +1.2 Aug +0.2 (6/8); 2x latency +0.20c (CI -3.0..+3.4) | the whole edge is Jan-May; Jun-Aug is ~+0.3c on 906 mkts |
| 5 | 10-18 | v1 unchanged | lockbox (Sep 1-Oct 17) | **fail** -0.36c/ct, CI -4.2..+3.8, 569 mkts, 21/47 days | decay confirmed out of sample |

## Learnings
- The plain SOL open reversal passed the pooled full test only on Jan-May; from June it is flat (+0.3c) and the lockbox is -0.4c. The pooled CI "promising" verdict hid a regime change that the 2x-latency run (+0.2c) and the Jun-Aug months showed. The open reversal is arbitraged away on SOL (as screened on all coins by sol-screens).
- Maker entry doesn't fix it (ad hoc, see iteration 1).

## Status
rejected (lockbox fail). Do not rerun.
