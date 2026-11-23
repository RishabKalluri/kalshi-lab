# SOL zfav maker, early window (sol-zfav-early)
Agent run 20261105-0059-2. derived_from sol-zfav-maker; same family and lockbox evidence.

## Hypothesis
See config.json. Diagnosis of sol-zfav-maker Jun-Sep fills by time to close (c/ct): 350-430 s +2.5, 280-350 +0.85, 200-280 -0.1, <200 -2.4. Ad hoc start_tau=540 stop_tau=300: Sep 1-15 +4.07c (397 mkts, t 4.9), Jul 1-15 +1.87c (238), Jun 1-15 +2.47c (255); parent on Sep 1-15 +1.23c.

## Log
| # | change | stage | result |
|---|---|---|---|
| 1 | smoke ok, quick passed noise -1.13c (117 mkts, CI -6.8..+3.7); full 1/3 queued sol-zfav-early-1105-014932 | | |
| 2 | full 1/3 (job sol-zfav-early-1105-014932): PROMISING +2.27c/ct, CI +1.61..+2.95, 4,784 mkts, 9/9 months positive (Jan +13.5 [77 mkts], Feb +3.1, Mar +0.03, Apr +4.8, May +1.7, Jun +2.3, Jul +1.6, Aug +1.1, Sep +2.1), 2x latency +1.78c. Parent +1.18c | | |
