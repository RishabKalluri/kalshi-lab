# XRP+DOGE zfav maker, early window

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

## Run log (agent run 20261108-0056-1)
- Rule: sol-zfav-early unchanged on XRP+DOGE (540..300 s, z>=1.5), fixed in advance.
- smoke ok; quick (xrpdoge-zfav-early-1108-010020) passed +1.45c, CI -2.3..+4.7, 218 mkts (noise).
- Full 1/3 job xrpdoge-zfav-early-1108-010057 queued 01:00; still running ~7 h later (shared worker). Read results.json for the verdict.
  Promising -> lockbox (same family and held-out days as the other zfav members); otherwise leave as is.
- **Full 1/3 promising**: +1.98c/ct (CI +1.51..+2.45), 9,592 mkts, 145/197 days positive, max drawdown 95. Lockbox job queued at the end of the run (see results.json).
