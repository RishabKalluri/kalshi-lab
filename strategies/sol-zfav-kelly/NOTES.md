# SOL zfav maker, gap-proportional Kelly (sol-zfav-kelly)
Agent run 20261110-0057-2. derived_from sol-zfav-early; same family/lockbox evidence as the zfav makers.
Pick rationale: SOL has had 12 rounds of dead screens; the one robust, repeated finding is the edge's dependence on
favourite price. This turns that into entry + sizing (a variation, not a new edge; disclosed).

## Hypothesis
See config.json. Fixed before testing: k=0.5, gmin=0.03, zmin=1.0, kelly:0.25 (max 5% of equity per market).

## Log
| 1 | smoke ok; quick passed +4.88c (89 mkts, CI -2.1..+10.9); full 1/3 queued | | |
| 2 | full 1/3 (sol-zfav-kelly-1110-010023): PROMISING +4.09c/ct, CI +2.90..+5.27, 2,998 mkts, 8/9 months positive (Jun -0.9c; Mar +1.2, Jul +1.1), 180/251 days, 2x-lat pooled +4.33c. Parent sol-zfav-early +2.27c. Lockbox job sol-zfav-kelly-1110-050337 queued | | |
