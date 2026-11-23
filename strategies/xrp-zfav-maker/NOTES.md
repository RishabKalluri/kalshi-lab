# XRP spot-confirmed favourite, maker entry (xrp-zfav-maker)
Agent run 20261102-0056-2. derived_from sol-zfav-maker (rule unchanged, moved to XRP; no tuning).

## Hypothesis (before testing)
See config.json. Signal z = D/(rv15 sqrt(tau)) >= 1.5; post-only one tick inside the spread, tau 420..150 s, ttl 30 s, hold to settle.
Ad hoc evidence came from two 2-week windows on dev data (Jul 1-15, Sep 1-15) with the SOL parameters untouched.

## Log
| # | change | stage | result |
|---|---|---|---|
Ad hoc engine windows, development dates, SOL parameters untouched (z 1.5, tau 420..150, ttl 30), all maker fills (research-grade, not the pipeline):
| window | markets | c/contract | t |
|---|---|---|---|
| Jun 1-15 | 493 | -0.63 | -0.5 |
| Jul 1-15 | 515 | +1.85 | 2.2 |
| Aug 1-15 | 492 | +1.75 | 2.0 |
| Sep 1-15 | 726 | +2.57 | 3.1 |
| Sep 16-30 | 711 | +2.00 | 2.7 |
Same rule on SOL: Jul 1-15 +0.02c (306 mkts), Sep 1-15 +1.23c (585 mkts, t 1.4); the SOL taker rule gave +1.24c on Sep 1-15 (200 mkts).
Smoke queued (job xrp-zfav-maker-1102-024952) behind three 5-coin full tests on the worker; the full 1/3 follows when it clears.
More ad hoc windows (same params): Jun 16-30 +0.88c (545 mkts, t 0.9), Jul 16-31 +1.04c (507, t 1.2), Aug 16-31 +1.74c (793, t 2.1). XRP so far: 7 of 8 half-months positive, 5,282+ markets.
Remaining ad hoc windows: May 1-15 +0.30c (399 mkts, t 0.2), May 16-31 +0.46c (496, t 0.4). Full XRP table: 10 half-months May-Sep, 9 positive, ~5,700 markets, market-weighted mean about +1.3c, rising over time (May +0.4, Jun +0.1, Jul +1.4, Aug +1.7, Sep +2.3).
DOGE (same rule, ad hoc, no folder): Jun 1-15 +1.24c, Jun 16-30 +3.13c (t 4.1), Jul 1-15 +0.63c, Jul 16-31 +2.20c (t 2.6), Aug 1-15 +2.71c (t 3.2), Sep 1-15 +1.27c, Sep 16-30 +2.70c (t 3.9): 7/7 positive, ~3,500 markets, mean about +2.0c.
These are single engine runs with a parameter-free rule on development dates (no fit), so close to a walk-forward, but they are not a pipeline result: no 2x latency run, no ledger entry, no lockbox. Status: developing; the smoke (xrp-zfav-maker-1102-024952) and sol-zfav-maker's full 1/3 are queued; when the XRP smoke passes, queue quick then full 1/3, then the lockbox (recorded XRP books exist from Oct, so the lockbox also tests fills on real books). Consider a DOGE folder (rule unchanged, derived_from sol-zfav-maker) and/or one pooled XRP+DOGE+SOL run to save worker time.
