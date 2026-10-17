# Flow-Vol

Markets: KXBTC15M (primary; ETH lockbox is spent by eth-volfav family, SOL flow gain ~0)

## Hypothesis (written before any test)
- Why mispriced: Kalshi implied vol is anchored on price-based realized vol. Per-second order flow (volume, trade
  counts, largest trade) leads vol, so a HAR+flow forecast separates "vol high and fading" (buy the favourite) from
  "vol high and persisting" (don't).
- Other side: takers pricing the late-window favourite off recent price moves only.
- Wrong if: full walk-forward CI not above 0 or <60% months positive.

## Research (development data < 2026-08-20; research/r2.py, top.py)
- OOS R2 of log next-window rv (train Dec-Apr, test May-Aug), HAR+hour+h: BTC .517 -> .536 (+.019; +rv5 alone .530),
  ETH .714 -> .736, SOL .763 -> .765 (rv5 alone .776: no flow gain). Gain positive in 6/6 months for ETH, 5/6 BTC.
  Mostly volume + trade-count level; largest-trade and perp share/imbalance add ~0.
- Top-30% implied/forecast favourite at next fill after fees (rows, not independent): BTC HAR +0.21c, flow +0.61c (se .37);
  ETH both +0.68c; SOL +0.19c. One row per market: BTC -0.54c, ETH +0.08c (se .54): i.e. not distinguishable from 0.
  Higher thresholds (top 5-10%) look better (BTC +1.0 to +1.9c, se .7-1.0) but that is picking after the fact.
- Verdict of the screen: forecast improves, trading value small and noisy. Lean to pipeline per workflow.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-13 | v1 BTC HAR+flow, pct .8 | smoke ok; quick passed (+2.3c, CI -3.0..7.5, 179 mkts); full PROMISING | +1.40c/contract, CI [0.06, 2.66], 3420 mkts, 6/7 months positive (Mar -6.9c), 2x latency +1.78c CI [-0.02, 3.63] | thin edge, CI lower bound near 0; going to lockbox as rules say |
| 2 | 10-13 | lockbox, unchanged code | lockbox FAIL | -4.17c/contract, CI [-5.84,-2.32], 2402 mkts, 11/55 days positive, max DD 1678 | in-sample +1.4c was noise/regime; idea rejected |

## Learnings
- Flow improves vol forecast R2 by ~0.02 (volume and trade counts; largest trade, perp share, imbalance add nothing) but that did not translate to a tradable edge: development +1.4c with CI lower bound 0.06 collapsed to -4.2c on the lockbox. A forecast R2 gain of 0.02 is too small against Kalshi's pricing noise. The implied-vs-forecast favourite buy (eth-volfav family) looks fragile outside ETH.

## Needs from user if it ever passes
Live flow stream (recorder doesn't stream flow yet) for paper/live.

## Current status
- Stage: REJECTED at lockbox.
