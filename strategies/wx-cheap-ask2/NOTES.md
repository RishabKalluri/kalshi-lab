# KXHIGH cheap-bracket offers, other cities

Markets: KXHIGHAUS

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

# wx-cheap-ask2 (agent run 20261024-0058-2)
wx-cheap-ask's rule (WxMaker, sides=ask, mid 2-10c cheap offers until 13:00 local) unchanged on KXHIGHAUS/LAX/TDAL, cities the parent never saw (parent used NY/CHI/MIA only because of memory). Only code change: KXHIGHTDAL added to the TZ table (America/Chicago; it would have defaulted to New York). Parameters fixed in advance; no tuning. Chosen because the SOL screens were exhausted and this is independent-market replication of a maker edge that passed a full test and a weak lockbox.
Hypothesis: see config.json. Counts as same family as wx-cheap-ask (derived_from).

| # | stage | result |
|---|---|---|
| 1 | smoke | no fills in the 6 h late-Aug night window (expected, as parent); folder needed chmod g+w for the worker |
| 2 | quick | passed +1.63c, 17 mkts (noise) |
| 3 | full 1/3 | queued (job wx-cheap-ask2-1024-010650) |
