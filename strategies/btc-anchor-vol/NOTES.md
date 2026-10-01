# BTC-Anchored Vol

Markets: KXETH15M (primary), KXSOL15M (second); KXBTC15M is read as an input, never traded.

## Hypothesis (written before any test)
- **Why the market should be mispriced:** eth-volfav showed ETH's 15-minute market misprices the *level* of
  short-horizon vol, and that BTC's market prices vol correctly. sol-vomma found the same pattern on SOL in
  the walk-forward but it failed the lockbox in September, i.e. a backward-looking HAR forecast can go stale
  when the vol regime moves. BTC's Kalshi market is deep and efficient, so its implied vol is a real-time,
  forward-looking vol forecast that already includes news, scheduled events and regime changes. ETH/BTC (and
  SOL/BTC) realized-vol ratios are much more stable than vol levels. So a fair ETH implied vol is
  iv_BTC x (ETH/BTC vol ratio). When ETH's own implied vol sits far above that, ETH's favourite is cheap;
  far below, its underdog is cheap (a two-sided signal, unlike eth-volfav).
- **Who is on the other side:** thin-market ETH/SOL traders and makers who price vol off recent ETH moves or
  intuition rather than off the deep BTC market (lottery-ticket underdog buyers when ETH iv is high;
  favourite chasers when it's low).
- **What would prove it wrong:** (1) the BTC-anchored forecast predicts ETH's future realized vol no better
  than the HAR model; (2) at real next fills, after fees, the top/bottom deciles of ETH iv / anchored iv
  aren't positive in both halves of development data; (3) walk-forward months mostly negative, or the edge
  is just eth-volfav's (check overlap).

## Ideas and prior work used
- `strategies/IDEAS.md` "Cross-market consistency (ETH vs BTC Kalshi)" and "BTC leads ETH/SOL".
- `strategies/eth-volfav/` (implied-vol math, HAR forecast, fixed checkpoints), `strategies/sol-vomma/`
  (lockbox failure in September).
- `strategies/settle-lockin/` (this session's first hypothesis, rejected at research: the market prices the
  settlement average correctly in the final minute).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-01 | side check before the main screen, `research/early_screen.py`: is a plain spot-distance model (Φ(D/σ√(h−40)), σ = geometric mean of rv 15m/60m/4h × k fit on Jan–Apr) better than the market *early* in the window (h ≥ 480), where our Binance-vs-CF basis error is small relative to the remaining move? | research | No: next-fill mid beats the model at every horizon 60–840 s on both coins (ETH h=600: 0.557 vs 0.547; SOL 0.547 vs 0.540). Trading model edges > 6¢ at h ≥ 480: ETH −0.2..−3.5¢ in 7/8 months, SOL negative in 6/8 | The market's fair value isn't worse than ours early in the window either. Only market-relative signals are worth testing. |
| 2 | 10-01 | `research/anchor_screen.py`: built `research/data/KXBTC15M.parquet` (dev only). Forecast log rv_fut of ETH/SOL with HAR vs HAR + log BTC Kalshi implied vol (+ coin/BTC rv ratio), fit Jan–Apr, test May–Aug 19; then deciles of log(coin iv) − forecast, favourite and underdog PnL at real next fills | research | **BTC implied vol adds nothing**: out-of-sample R² HAR 0.589 vs 0.587 with BTC iv (ETH), 0.591 vs 0.588 (SOL); BTC iv + ratio alone 0.24 / −0.11. Top-30% sets overlap 93% (ETH) / 97% (SOL) with plain HAR; the extra rows the anchor adds are ≈0 or negative in May–Aug. The two-sided idea fails too: buying the underdog when ETH iv is *low* vs forecast loses in both halves | BTC's Kalshi price (trade-implied, defined in only 50% of rows) carries no vol information beyond the coin's own trailing vol. The only vol-level edge is eth-volfav's (top HAR decile, favourite side). **Rejected.** |
| 3 | 10-01 | `research/bias_scan.py`: structural biases at next real fills, both coins, both halves: YES vs NO, price bucket, weekend × hour | research | Favourite-longshot pattern: buying underdogs (10–50¢) loses 2–4¢/ct, buying favourites ≈ −1..+1¢; no YES/NO preference beyond that; no weekend/hour cell positive in both halves on both coins | Nothing to take. The underdog overpayment is what `strategies/dog-seller/` tries to collect as a maker. |

## Learnings
- **BTC's Kalshi implied vol doesn't forecast ETH/SOL vol beyond their own HAR terms** (R² unchanged to the third
  decimal). The cross-market anchor is not the missing piece for the vol-level signal's September weakness.
- Early in the window (h ≥ 480 s) our spot-distance fair value still loses to the market's next fill, so
  "our model vs the price" is dead at every horizon on ETH and SOL, not just late.
- Favourite-longshot bias exists on both coins (underdog takers lose 2–4¢), but taking the favourite side
  doesn't profit after costs; only a maker could collect it.

## Current status
- Stage: **rejected at research** (no pipeline run: both the forecast test and the decile test failed their
  pre-stated criteria). Nothing to retry.
