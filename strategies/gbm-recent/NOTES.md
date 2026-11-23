# GBM edge, rolling 90-day fit

Markets: KXSOL15M

## Hypothesis (written before any test)
- Why the market should be mispriced:
- Who is on the other side, and why they keep losing:
- What result would prove this wrong:

## Ideas and prior work used
- (Other strategies' NOTES.md / results.json, research scripts, external sources you drew on.)

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|

## Learnings
- (Durable lessons, positive and negative, for future strategies to read.)

## Current status
- Stage:
- Next step:

# gbm-recent (agent run 20261028-0058-2, derived_from gbm-edge)
Hypothesis: gbm-edge's learned edge faded through the dev months (Aug -2.4c, SOL ~0 from July); refit monthly on only the previous 90 days instead of all earlier data so the model tracks the current regime. Everything else identical to gbm-edge (same features, thr 0.03, checkpoints 600..60 s). Stated from gbm-edge's dev monthly PnL, not from lockbox.
Wrong if: full walk-forward not promising / worse than gbm-edge's later months, 2x latency loses, lockbox loses. Risk: fewer training rows; synthetic last-trade books flatter stale quotes.

| # | change | stage | result |
|---|--------|-------|--------|
| 1 | v1 | smoke | ok |
| 2 | v1 | quick | passed, 12 mkts, +1.86c (CI -15.0..+22.5, noise) |
| 3 | v1 | full 1/3 (job gbm-recent-1028-010522) | still running at the agent's deadline (>5 h, as gbm-edge's was); read results.json |

Status: developing. Lockbox only if full is promising and clearly better than gbm-edge in Jun-Aug. Note the family (gbm-edge) already used the lockbox on the same held-out days (+4.79c, CI -0.35..+9.95), so a pass here is weak, not independent, evidence.

## Pickup (agent run 20261104-0059-2)
Full 1/3 was promising: +3.86c (CI +2.19..+5.52, 2,933 mkts; months May +4.7, Jun +3.0, Jul +2.8, Aug +0.75; 2x latency pooled +1.65c, Aug +0.41c). The edge is fading, so the lockbox (Oct 1 onward; fresh held-out days, gbm-edge's earlier lockbox covered Aug 20-Sep) is the informative test. Queuing the single lockbox run for this period with the code unchanged.
