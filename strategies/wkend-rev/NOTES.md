# Weekend open reversal (5 coins)

Markets: SOL, ETH, BTC, XRP, DOGE 15m. derived_from eth-overreact (plain z15 reversal), restricted to Sat/Sun UTC.

## Hypothesis (before any pipeline test)
- Weekday z15 reversal decayed to ~0 after May on every coin; weekends keep a premium on all five coins in both halves
  (screen, next-fill after fee, |z15|>1.25, mid 25-75c): weekend-weekday gap SOL +2.4/+1.8c, ETH +2.4/+1.4, BTC +9.0/+2.0, XRP +4.8/+1.2, DOGE +4.5 (Jan-Apr / May+).
- Other side: thin weekend retail quoting at the open.
- Wrong if: pooled full CI includes 0, <60% months positive, 2x latency loses, or lockbox loses.
- Caveat: the weekend split was found by screening development data (post hoc, one split tried), so the lockbox decides.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 2026-10-19 | v1 | smoke | ok (forced fills with z_thr 0.3, weekend_only 0) | |

## Current status
- Stage: quick.

## Results
- Quick: +6.0c, 126 mkts (noise-level). Full 1/3 (wkend-rev-1019-014104): **promising** +1.96c/ct, CI +0.16..+3.64, 3,382 mkts, 35/58 days; months Mar +11.2, Apr +5.1, May -1.3, Jun +0.5, Jul +3.2, Aug -0.8 (4/6); 2x latency +0.89c (CI -1.5..+3.4). Edge concentrated in Mar-Apr, fading.
- Lockbox queued as wkend-rev-1019-043426, unfinished at session end; check results.json. Expect at best a weak pass.
