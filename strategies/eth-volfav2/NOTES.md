# ETH VolFavorite v2

Markets: KXETH15M (Kalshi 15-minute ETH up/down; YES if the 60s average of CF Benchmarks ETH RTI before close
is at least the 60s average before open).

Same signal, model and parameters as `eth-volfav` (see its NOTES.md for how it works). Two execution fixes for
live data only; backtests on backfill are unchanged. eth-volfav keeps trading live and on paper untouched, so v2
runs as a separate paper trader beside it.

## Hypothesis (written before any test)
- **Why the market should be mispriced:** same as eth-volfav: ETH's 15-minute market overprices short-horizon
  volatility, so late in the window the favourite is cheap when implied vol is well above a forecast.
- **Why v2:** live, v1 doesn't trade the strategy that was validated.
  1. `rv_scale=1.09` came from one partial day (Sep 29, ~3 good hours). Re-measured over Sep 29–Oct 11 (219 clean
     hours): the Binance/live-composite rv ratio the forecast sees is about **1.02** (IQR 0.95–1.08); week 40 1.04,
     week 41 1.01. At 1.09, v1 crosses the threshold on ~73% as many checkpoints as its backtest.
  2. Feed gaps: v1 adds the whole squared jump across a gap (recorder outage, or all three venues stale) as one
     1-second change, which inflates rv15/rv60/rv4h for up to 4 hours and suppresses trades. ~27% of checkpoints
     Sep 29–Oct 11 had composite gaps in their windows.
- **Who is on the other side:** as eth-volfav.
- **What would prove this wrong:** on paper, the extra trades v2 takes (that v1 doesn't) lose clearly, or v2's
  ¢/contract falls well below eth-volfav's paper/live over the same markets.

## Ideas and prior work used
- eth-volfav (strategy, model, params copied unchanged; `params/vol_model_KXETH15M.json` is its live fit).
- rv_scale re-measurement: scratch analysis in the main session (composite rebuilt exactly as `ctx.spot`:
  median of fresh Coinbase/Kraken/Bitstamp; eth-volfav's beta-weighted rv15/rv60/rv4h at the 7 checkpoints).
  Ratio rises with vol (0.89 quietest fifth of hours → 1.10 busiest), weekends 0.91 vs weekdays 1.04. SOL 1.12
  (confirms sol-midrev's 1.11).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-12 | gap-safe rv: a change across a g-second gap adds (Δ²)/g | backtest | backfill Jul 1–15 identical to eth-volfav (188 markets, 1,490 contracts, same PnL) | Binance 1s backfill has no gaps, so the fix only matters live |
| 2 | 10-12 | pipeline smoke + quick | quick | smoke +13.7¢/ct (10 markets); quick passed +6.6¢/ct (99 markets, CI −0.7..+12.5) | same as v1, as expected. No full test: it would replay v1's walk-forward exactly |
| 3 | 10-12 | rv_scale at real signal times: replayed recorded books Sep 29–Oct 10 through `_consider` (calibration only, no P&L or outcomes) | calibration | Binance/live ratio 1.016 at all clean checkpoints, 1.013–1.015 at unbiased signal selections; live crossings 269 at 1.09 → 381 at 1.02 (+42%; backtest-equivalent 463). Gaps distorted 31% of checkpoints and cost ~a quarter of signals | rv_scale=1.02 |
| 4 | 10-12 | `paper-start` rv_scale=1.02, slip_c=1, 0.5%/order | paper | running as kalshi-paper@eth-volfav2 | |
| 5 | 10-13 | capacity: replayed recorded books Sep 29–Oct 12 through v2, book at decision and +150 ms (605 would-be orders; no P&L) | calibration | depth on the buy side median 92 at the touch, 569 within +1¢, 1,145 within +2¢. IOC slippage vs size (+2¢ limit): 100 ct 0.28¢, 200 ct 0.44¢, 500 ct 0.67¢, 1,000 ct 0.94¢. ~48 signals/day on ~29 markets (1.65/market). Cleared levels rarely refill within 5 s | capacity is far above live size (~3 ct). Use +2¢ limit from ~100 ct; assume later checkpoints in the same market fill ≥1¢ worse |
| 6 | 10-14 | paper vs v1 paper, Oct 12 22:40 - Oct 14 03:00 (~28h) | paper | v2 22 markets, 203 ct, +$28.17 (+13.9¢/ct); v1 15 markets, 143 ct, +$19.08 (+13.3¢); shared 14 markets +14.3¢; v2-only 8 markets +12.6¢ | +47% markets as calibrated; extra trades too few to judge |
| 7 | 10-14 | live: replaces v1 in tmux live-eth-volfav ($1,000, 1%/order, rv_scale=1.02, slip_c=1) | live | started 03:05 UTC, flat at switch | user chose to switch before the planned 10-day check |

## Learnings
- **Calibrate live-vs-backtest inputs over weeks, not one day.** One partial day gave 1.09; two weeks give 1.02.
- **Running sums over samples need gap handling** whenever the live feed can drop out.
- **ETH's book is much deeper near the touch than backfill's `book_depth=43` suggests** (median 92 at the touch,
  ~570 within 1¢ at signal times), so backfill tests understate capacity; they don't test the edge at large size.

## Current status
- Stage: **live** since Oct 14 03:05 UTC ($1,000, 1%/order, rv_scale=1.02, slip_c=1, stop-loss $200; tmux `live-eth-volfav`). Paper continues beside it; eth-volfav (v1) paper is the comparison for the extra trades.
- Next: compare v2's extra trades vs v1 paper (~150 orders, ~Oct 22-26). If they lose clearly, move live back to v1 (user's OK). rv_scale re-check after 2 more weeks of recordings.
