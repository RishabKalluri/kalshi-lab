# Rain maker (rain-maker)

Agent run 20261017-0100-1. derived_from rain-no (other agent's folder; not edited). Markets: KXRAIN, real recorded books since Jul 16
(backfill/books; rain-no's NOTES say "backfill has no books" and used a book synthesized from trades).

## Hypothesis (written before the pipeline runs)
- Why mispriced: rain-no's mechanism: retail prices a forecast chance of rain; the market resolves on >0.00 in at the station; YES takers lose
  7-17c/ct. A maker offering YES collects the ask from these buyers and pays no fee.
- Who is on the other side: retail YES buyers (but some are informed once rain is visibly falling at the station: the adverse selection).
- Wrong if: pooled walk-forward CI <= 0 (city-day clusters), 2x latency loses, or the Sep 1+ lockbox (autumn fronts) loses.

## Research (ad hoc engine runs on dev days only, Jul 16 - Aug 31, fixed 10 contracts, 7 weekly chunks)
- rain-no's rule as taker on the real books (hit the YES bid when 10-90c, last 6 h, one per market): +9.59c/ct, CI +4.49..+14.21, 210 mkts,
  1,377 contracts, 31/42 days (synthetic-book full test said +14.1c). So the edge survives real quotes, ~1/3 smaller.
- Same window, post-only offer at the best ask (mode=maker): +16.75c/ct, CI +8.54..+23.05, 181 mkts, 6,298 contracts, 37/42 days, Jul +29.9c, Aug +13.0c.
Both decided before looking (mode and window copied from rain-no v2; no tuning).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-17 | v1 (defaults: maker, last 6 h, bid 10-90c, 40 max short, ctx.size) | quick (Aug 29-31) | passed +8.8c, 8 mkts, CI -0.8..+31.8 | noise (first attempt lost the result to a results.json PermissionError: folder was not group-writable; reran) |
| 2 | 10-17 | v1 | full (Jul 16 - Aug 31, books) | **promising** +16.78c/ct, CI +9.78..+23.34, 181 mkts, 7,655 contracts, 36/42 days, Jul +28.8c (10/11 days), Aug +12.9c (26/31); 2x latency +16.62c | full 1/3 used |
| 3 | 10-17 | v1 unchanged | **lockbox** (Sep 1 - Oct 12 books + recorded Oct 13-16) | **pass**: +5.84c/ct, CI -0.26..+12.01, 139 mkts, 6,453 contracts, +$376.6, 27/40 days; Sep +6.2c (116 mkts), Oct 1-12 +3.8c (23 mkts); **recorded books Oct 13-16: -7.1c (17 mkts, 987 contracts, CI -31.9..+12.9)** | the edge shrank by ~2/3 out of sample (16.8 -> 5.8c), like rain-no (14.1 -> 4.5c) |

## Learnings
- Real books for KXRAIN exist from Jul 16, so rain-no can be checked on real quotes: its taker rule nets +9.6c/ct there (vs +14.1c on the synthetic book).
- A post-only offer at the touch gets ~4.5x the volume of the taker rule and +16.8c/ct in development: retail YES buyers lift the ask and no fee.
- Out of sample (Sep 1 - Oct 12) both rain strategies keep about a third of the dev edge; the CI includes zero. The 4 live-recorded days (Oct 13-16) lose for both
  (-7.1c here, -11.5c rain-no), 17 markets: the only genuinely live book data, too small to conclude but it is what paper trading must resolve.
- Rain is correlated across cities (frontal days): ~84 effective clusters for the whole development+lockbox record, one season (Jul-Oct).
- Quick/smoke on weather are 3-day windows: noise.

## Current status
- **paper_candidate** (lockbox passed 2026-10-17, weak pass). Full tests used 1/3, lockbox 1/1 for this period. Family: rain-no (their pass and mine are one piece of evidence).
- Before live: `kalshi-lab audit rain-maker`; results.json must match the ledger. Paper first: needs the real KXRAIN books (recorded since Oct 13) to confirm that
  the offer at the ask gets filled at that price and that Oct 13-16 loss was noise; sizes are tiny vs book (maker queue).
- Risks: one season; tail (a short YES at 90c loses 90c on rain; max short 40/market); correlated cities; informed YES buyers when rain has started.
