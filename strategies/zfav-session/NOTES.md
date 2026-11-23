# zfav Asia/EU session (zfav-session)
Agent run 20261109-0055-1. derived_from zfav-wide (same family/lockbox as the zfav members).

## Hypothesis (written before the pipeline runs)
- Mispricing: spot-confirmed favourites (z>=1.5, 4-8 min left) are under-priced. Screen on the 5-coin research dataset (Dec-Aug,
  taker next fills net of fee, ask<=97c): windows closing 04-11 UTC earn +1.7..+2.1c (se ~0.3), +2.07c Dec-Apr / +1.72c May-Aug,
  every coin 1.6-2.0c, 9/9 months; closes 12-15 UTC (US morning) lose -0.7..-1.1c; the rest +0.4..+0.6c.
- Other side: flat-vol quoters/retail in thin Asia-EU hours; in US hours informed flow already prices the favourite.
- Wrong if: walk-forward CI<=0, <60% months positive, 2x latency loses, lockbox loses.
- Caveat: the session was picked after seeing 4-hour blocks (post hoc); zfav-wide lockboxed at +0.27c (edge decaying in Oct).
- Also seen: edge rises with Kalshi trade count (quartiles +0.3,+0.5,+1.0,+1.2c), not a thin-market effect.

## Iteration log
| # | change | stage | result |
|---|---|---|---|
| 1 | v1 | smoke (all hours; default 18-24 UTC window is outside the filter) ok | |
| 2 | v1 | quick | passed +2.52c, CI -0.58..+5.14, 148 mkts, 2/3 days |
| 3 | v1 | full 1/3 queued | |

Full 1/3 job zfav-session-1109-010345 still running at run end; read results.json.

## Lockbox pickup (agent run 20261110-0056-1)
Full 1/3 was promising (+1.80c, CI +1.31..+2.26, 7,977 mkts). Params unchanged; lockbox job zfav-session-1110-005841 queued 2026-11-10 ~01:00 UTC and still running (>5 h, shared worker) at this run's deadline. Read results.json for the verdict. Session cut was chosen post hoc and zfav-wide lockboxed at +0.27c, so a pass is weak evidence (same family).
