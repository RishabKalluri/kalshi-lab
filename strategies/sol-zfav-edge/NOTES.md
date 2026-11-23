# SOL favourite taker, model-edge entry

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

# SOL model-edge favourite taker (derived_from sol-zfav-px) - agent run 20261109-0056-2
Hypothesis: enter when Phi(z) - ask >= 3c (z>=1.0, ask<=95c); dev screen net return monotone in that edge. Same family as sol-zfav-px, whose lockbox was flat (+0.006c), so prior is low.
| # | stage | result |
|---|---|---|
| 1 | smoke | no fills in 6 h window (not an idea failure) |
| 2 | quick | passed, 15 mkts, noise |
| 3 | full 1/3 (sol-zfav-edge-1109-044906) | still running at the run's deadline; read results.json |
Status: developing. Next: if full is promising, ONE lockbox run; given sol-zfav-px's flat lockbox, treat any pass as weak family evidence.
