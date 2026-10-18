# ETH+BTC volume-confirmed reversal (eth-volrev)
Agent run 20261017-2159-2. derived_from sol-volrev (rule unchanged: z_thr 1.25, relv_thr 2, checkpoints 870-780, mid 300-700). Pre-registered: no parameter changes for ETH/BTC.
Chosen because it's the only passed-strategy variation with data and flow files for BTC/ETH; sol-volrev's note said the ETH/BTC screen pointed the same way.
Caveat: threshold came from the SOL dev screen; family overlaps eth-overreact/midrev (one piece of evidence).

## Iteration log
| # | date | change | stage | result | learning |
| 1 | 10-17 | rule unchanged | smoke | no fills in the 6 h window (rare signal); ad hoc Jul 1-8 ETH: 47 fills | skipped smoke |
| 2 | 10-17 | same | quick | passed, -7.4c, 14 mkts (noise) | |
| 3 | 10-17 | rule unchanged | full 1/3 | **inconclusive** +1.52c/ct, CI -0.31..+3.43, 2,702 mkts, 53k ct, 129/247 days; months +0.15,+1.7,+7.6,+0.8,+0.9,-3.0,+0.2,+1.1 (7/8 +, Dec +29 on 24 mkts); BTC +1.26c, ETH +1.81c; 2x latency -0.83c (CI -3.8..+2.2) | consistent sign on both coins but small and not latency-robust; no lockbox |
| 4 | 10-17 | v2: relv_thr 3 (SOL dose-response: >3 +5.7c vs >2 +4.1c; stated before running) | full 2/3 queued | pending | |
