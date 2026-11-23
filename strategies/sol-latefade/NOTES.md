# SOL late-window fade

Markets: KXSOL15M (derived_from sol-midrev: same signal z15, entered late in the window instead of at the open)

## Hypothesis (written before any pipeline test)
- Why mispriced: the previous window's large move (|z15|>1.25) reverses on average; thin SOL quotes stay anchored to the
  trend late in the window (screen: fade nets +4..+8c at h=120-240 s on SOL, y-mid +8.2c at 180 s, se 2.5; ETH ~+1, DOGE +5, BTC/XRP ~0).
- Other side: late takers/quoters extrapolating the window's path.
- Wrong if: full CI includes 0, <60% months positive, Jan-Apr only, 2x latency loses, or lockbox loses. Selection risk:
  only SOL looked positive of five coins, and h=240 move_fut z was ~0 while h=180 was +0.14 (inconsistent) -> may be noise.

## Screens (research/data/KXSOL15M.parquet, dev only; scripts in the agent run folder s/)
- Multi-timescale boundary reversal (z over 1h, 4h, 24h): only the 15-minute z1 reverses; 1h/4h/24h moves *continue* (fade loses 3-10c). Nothing new.
- z1 fade by entry time h (|z1|>1.25, mid 20-80, next fills): Jan-Apr big at h>=600 (+5..+9c), Jun-Aug ~0 or negative at h 300-720 but +3..+5c at h 60-240.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 2026-10-19 | v1 z>1.25 h120-240 | smoke | ok (z_thr 0.3 only for the smoke fills) | folder perms must be g+w for the worker |

## Current status
- Stage: quick queued.
