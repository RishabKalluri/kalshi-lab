# gbm-edge: learned edge (GBM) on SOL/XRP/DOGE 15m (agent run 20261025-0056-1)

## Hypothesis
Thin 15m markets are priced off the last trade, not the spot-vs-strike distance. Two GBM regressors predict the net edge of buying YES at the ask / NO at the bid from z5 = D/(rv5 sqrt h), z60, mid, h; trade the better side if predicted edge > 3c, one entry per market, checkpoints 600..60 s. Wrong if the full walk-forward isn't promising, 2x latency loses, or the lockbox loses.

## Research (research/*.py, dev data only)
- screen2/4: walk-forward by month on the research dataset, next-trade fills: 3 coins +1.5..+2.2c (se 0.5, ~4,700 mkts / 5 months); 5 coins +1.7..+2.4c but BTC/ETH only ~+0.3c.
- screen3: a probability (classifier) version of the same features: -0.4c. The edge is in where the ask is wrong, not in a better probability.
- screen5: edge by age of the dataset ask: <=5 s +1.6c, >5 s ~+4c. Part is stale last-trade quotes; the engine's synthetic book is last-trade based, so it may flatter. Real books only exist in the lockbox.
- wx_*.py (weather) and sp_*.py (NBA/NHL): same learned-edge screen, dead (see run report).

## Iteration log
| # | stage | result |
|---|---|---|
| 1 | smoke | passed (2 mkts) |
| 2 | quick | passed, 27 mkts, -11.3c (noise) |
| 3 | full 1/3 (job gbm-edge-1025-010758) | still running at the agent deadline (>5 h); read results.json |

## Status
developing. Lockbox only if the full is promising; check per-coin cards and 2x latency. Setup note: agent-created folders need chgrp -R lab, chmod -R g+rwX, setgid params/ or fit() can't write.

## Continued by agent run 20261026-0054-1
- Full 1/3 came back **promising** (after the first agent's deadline): +3.76c/ct, CI +2.31..+5.31, 3,094 mkts, 76/123 days, lat2x +2.53c (CI -0.24..+5.42).
- Dev diagnosis (markets.csv, no new tests): by month +4.4 (May, 1,900 mkts), +4.4 (Jun, 615), +5.3 (Jul, 258, CI incl 0), **-2.4 (Aug, 321)**; by coin DOGE +3.7 / SOL +3.7 / XRP +3.8 (similar). Trade count falls 6x May->Aug as the model finds fewer mispricings
  (consistent with the activity growth noted in IDEAS.md); Jun-Aug pooled is ~+2.7c. Expect a weaker lockbox than the full. Running the lockbox as the designed next step; no code change since the full (code fingerprint unchanged).

## Run 20261026-0055-2 (picked up, no code change)
- Full 1/3 read: pooled +3.76c (CI +2.31..+5.31, 3,094 mkts, 76/123 days), lat2x pooled positive but much smaller. Monthly: May +4.4, Jun +4.4, Jul +5.3, Aug -2.4c.
- Split of dev PnL by coin and month (markets.csv of the wf runs), $: SOL 133/131/9/0.4 (May..Aug), XRP 505/110/170/-120, DOGE 576/126/64/-0.3. The edge fades on every coin and is gone on SOL from July; trades fell 1,900 -> 321 mkts/month. Expect the lockbox (Sep-Oct, real books) to be weak.
- Queued the one lockbox run (job gbm-edge-1026-005732, code unchanged). Another job (gbm-edge-1026-005755) was also running; at the time of writing neither had finished (>8 h). Read results.json for the verdict.
- Lockbox queued 2026-10-26 00:57 (job gbm-edge-1026-005755; a second lockbox job gbm-edge-1026-005732 for the same folder was queued 23 s earlier by another session). Still running after >6 h at the end of run 20261026-0054-1 (CPU-bound GBM calls per tick); read the verdict in results.json. If it fails, note that the full's edge was already fading (Aug -2.4c) and the stale-quote part of the edge may be an artefact of synthetic last-trade books.
