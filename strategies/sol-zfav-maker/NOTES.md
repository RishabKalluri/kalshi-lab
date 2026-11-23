# SOL spot-confirmed favourite, maker entry (sol-zfav-maker)
Agent run 20261102-0056-2. derived_from sol-zfav (signal unchanged, entry changed).

## Hypothesis (before testing)
See config.json. Signal: z = D/(rv15 sqrt(tau)) >= 1.5 (sol-zfav). Entry: post-only one tick inside the spread, tau 420..150 s, ttl 30 s, hold to settle.
Opportunities: sol-zfav screen had 4,037 signals May-Sep at tau 240/300 only; the continuous window gives more.
Prior: earlier maker tests on backfill (spreadmk, dog-seller, volfav-maker) were all adversely selected, so my prior is about 25% that this survives.
Wrong if ad hoc dev windows are <= 0 net, or too few fills.

## Log
| # | change | stage | result |
|---|---|---|---|
Smoke ok (job sol-zfav-maker-1102-013858), quick passed (-1.9c, 141 mkts, CI -6.9..+2.5, noise-level; job sol-zfav-maker-1102-013917). Full 1/3 queued as sol-zfav-maker-1102-013957 behind three 5-coin full tests: result lands in results.json when it runs.
Ad hoc: Jul 1-15 +0.02c (306 mkts), Sep 1-15 +1.23c (585 mkts, t 1.4); SOL taker rule on Sep 1-15 +1.24c (200 mkts). Decomposition of the Sep run: edge vs mid at fill +0.66c, adverse 30 s -1.04c, carry to settlement +1.60c.
Same rule on thin coins is stronger (see xrp-zfav-maker/NOTES.md; DOGE ad hoc Aug +2.7c, Sep +1.3c / +2.7c).
