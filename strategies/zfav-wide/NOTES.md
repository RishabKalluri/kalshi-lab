# Spot-confirmed favourite, wide price range (zfav-wide)
Agent run 20261101-0108-1. derived_from btc-zfav. Same mechanism and same held-out months as the zfav family (btc/sol/xrp/doge-zfav), so any lockbox pass counts as the same piece of evidence; what is new is the payoff: z>=2.5 and ask up to 98.5c across all five coins, ~35 entries/day.

## Hypothesis (before testing)
See config.json. Screens on the research dataset (Dec-Aug dev only):
- BTC-confirmation filter for alt coins (alt z with BTC z same sign/strength): adds nothing (XRP 2.3 vs 2.1c); dropped.
- Earliest checkpoint 120-480 s, z>=2.5, ask cap: 97c +1.85c (4.2k, 15/day); 98.5c +1.34c (9.6k, 35/day); 99.5c +0.86c (20k, 76/day); every cell 9/9 months. z>=3 similar.
- Chosen: z>=2.5, cap 98.5c (volume vs edge), checkpoints 480..120 step 60 (420 added).

## Iteration log
| # | change | stage | result |
| 1 | v1 | smoke ok; quick passed -1.14c (CI -4.0..+1.4, 188 mkts, 3 days: noise) | |
| 2 | v1 | full 1/3 queued (job zfav-wide-1101-011311), still running at the agent's deadline; read results.json | |

## Lockbox pickup (agent run 20261105-0058-1)
Full 1/3 came back promising (+1.26c, CI +0.95..+1.56, 8,903 mkts). Queued the lockbox for the new period: job zfav-wide-1105-005929 (still running at this run's deadline after ~5 h on the shared worker). Read results.json for the verdict. Same family/held-out months as the other zfav members.
