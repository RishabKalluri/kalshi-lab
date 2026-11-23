# XRP VolFavorite early, weekends

Markets: KXXRP15M

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

# xrp-volfav-wkend (agent run 20261024-0058-2)
xrp-volfav-early's rule traded only on windows closing Sat/Sun UTC (new param weekend_only=1; everything else unchanged). Motivation fixed before any run: volfav-pool's dev research found the edge ~2x on weekends in all five coins. Same family and held-out days as xrp-volfav-early.
| # | stage | result |
|---|---|---|
| 1 | smoke | no fills in the 2-hour weekend part of the smoke window (expected) |
| 2 | quick | passed +1.21c, 108 mkts (noise) |
| 3 | full 1/3 | job xrp-volfav-wkend-1024-030125 queued |
