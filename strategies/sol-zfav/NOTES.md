# SOL late spot-confirmed favourite

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

## Hypothesis (before testing)
btc-zfav's rule (buy the side spot is >= z sigma past the strike) on SOL at later checkpoints. Screen on development data
(Jan-Aug, taker next fills net of fee, research/data/KXSOL15M): tau 360 z>=1.5 +2.9c (850 trades, se 0.44, 8/8 months),
tau 240 +2.05c (576, 8/8), tau 300 +0.9c (864, 5/8); z>=2 larger but only ~100 trades each. Checkpoints 360/300/240 and
zmin 1.5 were picked from this screen (mild selection; no further tuning). Other side: quoters pricing favourites with
flat vol / holders exiting. Wrong if engine depth/latency erase it, <60% months positive, 2x latency negative.
Opportunities ~100-150 trades/month.

## Iteration log
| # | change | stage | result |
|---|---|---|---|
| 1 | v1 | smoke | ok |
| 2 | v1 | quick | passed +4.2c, 32 mkts (noise-level sample) |
| 3 | v1 | **full 1/3: promising** | +3.13c/ct, CI +2.41..+3.82, 2,356 mkts, 25.3k contracts, 8/8 months positive (Jan +9.1, Feb +2.1, Mar +2.2, Apr +1.2, May +1.9, Jun +2.2, Jul +0.2, Aug +2.0); 2x latency +1.65c (CI +0.41..+2.71); max DD $26 |
Learning: Jan carries a lot (excl. Jan about +1.8c); July thin. Lockbox next, code unchanged.
