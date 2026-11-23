# ETH+BTC zfav maker (ethbtc-zfav-maker)
Agent run 20261107-0100-1. derived_from sol-zfav-maker, rule and params unchanged (z 1.5, tau 420..150, ttl 30, max_px 97c).
Chosen because IDEAS.md's ready list was taken or screened dead; this is the one untested coin pair of the zfav maker family.
Prior ~30% (BTC/ETH efficient). Opportunities: ~2 series x ~2,500 mkts/month at the signal -> thousands of trades, enough power.
## Log
| # | change | stage | result |
|---|---|---|---|
| 1 | v1 unchanged | smoke ok; quick passed -1.33c (CI -4.5..+1.7, 355 mkts, noise) | full 1/3 queued |
| 2 | same | full 1/3 | promising +0.894c (CI +0.578..+1.208, 30,129 mkts, 192/291 days) |
| 3 | same | lockbox queued ethbtc-zfav-maker-1107-050220 | |
Full 1/3 promising; lockbox job ethbtc-zfav-maker-1107-050220 pending at run end (read results.json).
