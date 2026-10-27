# XRP VolFavorite, early checkpoints

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

## Result (agent run 20261021-0057-1)
xrp-volfav (eth-volfav2 code) with checkpoints only at 480/360/300/240 s before close; threshold refit on those horizons (vol_fit.H). Choice is DEV-INFORMED: a screen (hscreen.py in the run folder) showed XRP 60-180 s checkpoints at -0.2..-1.5c vs +1.4..+2.2c at 240-480 s; reason (stated): late takers are informed (xrp-tie), so late asks are adverse.
| # | stage | result |
|---|---|---|
| 1 | smoke / quick | ok / passed (146 mkts, +2.15c, noise) |
| 2 | full 1/3 | **promising** +2.10c/ct, CI +1.20..+3.05, 4,404 mkts, 5/5 months positive (Apr +2.7, May +2.4, Jun +0.2, Jul +3.7, Aug +2.1); 2x latency +1.98c (CI +0.58..+3.32); vs xrp-volfav +1.33c |
| 3 | lockbox 1/1 (Sep 1-Oct 20) | **strong pass** +2.50c/ct, CI +0.95..+3.87, 1,644 mkts, 36/50 days; xrp-volfav on the same days +1.45c |
Caveats: same family and same held-out days as xrp-volfav, so not independent evidence; the horizon choice came from dev screening (not the lockbox). Backfill books are synthetic: real fills at 240-480 s need checking in paper.
