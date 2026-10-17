# 9:30 Bell Underdog on XRP+DOGE (folder bell-alts)

us-hours-vol (ETH+BTC) found the 9:30 ET window has ~2x the vol of the prior window and Kalshi implied vol is ~0.3 log too low there; engine
result +4.3c, CI -1.5..+10.5 (6/9 months) was sample-limited (~240 markets). Its notes asked for more coins with the same bell: this folder
runs the same v2 rule UNCHANGED on KXXRP15M and KXDOGE15M (history Feb/Mar 2026 on, ~255 windows).

## Hypothesis 1 (before any test)
As us-hours-vol: Kalshi prices the 9:30 ET window off calm pre-open vol; the underdog (10-45c) is cheap. Retail-heavy thinner coins should
misprice it at least as much. Wrong if: placebo-like result, full walk-forward CI not above 0, <60% months positive, 2x latency loses, lockbox loses.
Wide quotes in the opening burst are a trap (max_spread 60 mills kept). Overlap: bell-pool (another agent) runs ETH+BTC, no overlap with these markets.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-14 | v2 unchanged on XRP+DOGE | smoke | failed: no fills (smoke window has no 9:30 ET) | expected |
| 2 | 10-14 | | quick | passed, 2 markets, -30c | noise |
| 3 | 10-14 | | **full 1/3: inconclusive** | **+4.18c/ct, CI -3.54..+12.49**, 2.8k contracts, 171 mkts, 4/6 months positive (Mar +31.4 n11, Apr -9.3, May +6.4, Jun +12.9, Jul +0.9, Aug -5.3); 2x latency +3.4c (CI -5.5..+13.4) | Same ~+4c as ETH+BTC, sample-limited again (171 mkts => CI +-8c). Not tuned. Lockbox not run (not promising). |

## Learnings
- The 9:30 bell effect on XRP/DOGE is the same size (~+4c) as on ETH/BTC but no more significant; pooling all four coins' 9:30 windows (~400 mkts) is the way to settle it (bell-pool covers ETH+BTC).

## Current status
parked after full 1/3 (inconclusive). Budget left: 2 full, 1 lockbox.
