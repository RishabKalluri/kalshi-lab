# SOL open-reversal ridge model (sol-revmodel)

Agent run 20261023-0056-2. derived_from sol-midrev (shares the midrev/volrev/overreact lockbox family).

## Hypothesis (written before any engine test)
- The SOL open-reversal pockets that survive (late-confirmed burst, heavy-volume move) are facets of one forced-flow
  overshoot into the 15-minute boundary; one fitted score (z1, zl, relv, clock) should concentrate the edge better than
  separate thresholds and adapt monthly as it decays.
- Other side: opening takers who price the new window as a coin flip.
- Wrong if: engine walk-forward CI <= 0; research fills (first-minute prints) overstate engine fills (known: sol-overreact
  research +4c vs engine +0.3c Jun-Aug); lockbox loses.

## Research (dev data, /tmp scripts, not saved)
Walk-forward monthly refit Apr-Aug, target = fade PnL at next real fill at h=840: pred>4c +5.2c (se 2.2, n=466, 5/5
months positive); pred>0 +0.1c; without zl feature +2.0c. sol-volrev's hand rule on the same windows +2.5c (n=401).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-23 | v1 ridge (alpha 30), thr 4c | smoke (thr=-0.02 only to force fills) | ok | params/ must be writable by the worker user (chmod a+rwX before first run) |
| 2 | 10-23 | same | quick | passed (16 mkts, +9.9c, noise) | |
| 3 | 10-23 | same | full 1/3 | queued (sol-revmodel-1023-011044) | |

## Needs for paper/live
Live Binance SOL volume stream (flow isn't streamed), rv_scale ~1.11.

## Full 1/3 (thr 4c): inconclusive
+1.58c/ct, CI -1.45..+4.54, 994 mkts, 4/6 months (Mar +0.6, Apr -2.0, May +5.1, Jun -2.0, Jul +9.2, Aug +6.8), 2x latency +2.46c (Jun-Aug). The engine traded ~2x the research count (Mar/Apr/Jun ~200 mkts/month vs ~90): early monthly fits are noisy. Research dose-response: pred>6c +8.1c (n=236, 5/5 months), >8c +9.5c (n=144), >10c +10.1c (n=88).
## v2 (full 2/3): thr 0.07. Dev-informed (chosen from the research dose-response, not from engine months), logged as such.

## Full 2/3 (thr 0.07): PROMISING
+7.82c/ct, CI +2.50..+12.83, 326 mkts, 6/6 months positive (Mar +6.0, Apr +0.8, May +18.4, Jun +1.1, Jul +17.4, Aug +13.7), 2x latency +8.28c (CI +0.49..+15.97). Caveat: thr chosen after v1 from research dose-response (one dev-informed change); fewer trades (~55/month). Going to the lockbox.

## Lockbox attempt 1 crashed (infrastructure, not a verdict)
Job sol-revmodel-1023-020048: 'OSError(39, Directory not empty)' in the worker's params/ restore: my fit cache wrote params/daily/ as the sandbox user, which the worker couldn't delete. No lockbox result was recorded in results.json. Fix: cache moved to the temp dir (rev_fit.CACHE), a code change, so full test 3/3 is rerun before the next lockbox attempt.
