# Open-reversal ridge score, BTC+ETH+SOL pooled (revpool)

Agent run 20261023-0056-2. derived_from sol-revmodel (rejected at its lockbox: -6.7c). Same features/ridge; one pooled
fit across KXSOL15M/KXETH15M/KXBTC15M (fit_model(series list)); thr 0.06 fixed before any engine run.
Research (dev, walk-forward Apr-Aug, /tmp/h10.py): pooled fit thr 4c +3.4c (n=1101, se 1.4, all 3 coins and 5/5 months positive), thr 7c +8.5c (n=199); per-coin fits thr 4c +3.2c, thr 7c +5.6c (SOL -7.3c n=70). Engine fills are expected to be worse (sol-revmodel: research +5.2c at 4c -> engine +1.6c).
Wrong if: engine CI <= 0, months flip, lockbox loses.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-23 | thr 0.06 | smoke ok / quick passed (2 mkts) / full 1/3 | inconclusive -0.63c, CI -5.97..+4.79, 296 mkts, months [('2026-03', -2.023, 26), ('2026-04', 0.75, 154), ('2026-05', -4.682, 66), ('2026-06', -8.885, 17), ('2026-07', 21.614, 8), ('2026-08', 0.392, 25)], 2x lat 0.031c | research fills flatter the engine again |

Status: rejected (no lockbox).
