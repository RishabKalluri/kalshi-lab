# Coinbase Premium Drift

Markets: KXBTC15M, KXETH15M, KXSOL15M.

## Hypothesis (written before any test)
- **Why mispriced:** US buyers and sellers (ETF authorised participants, US funds, US retail) trade on USD venues,
  above all Coinbase, and work large orders over hours. While they're working, Coinbase trades at a premium (or
  discount) to offshore USDT venues like Binance, and the global price keeps drifting the same way until the order is
  done. So a widening Coinbase premium should predict the next 15 minutes' return in its own direction. Kalshi's
  15-minute window opens at the strike (~50/50) and doesn't use cross-venue spreads.
- **Who is on the other side:** opening takers/quoters treating each window as driftless.
- **What proves it wrong:** corr(premium change or deviation, next 15-min return) isn't consistently positive in both
  halves (A: Dec-Apr, B: May-Aug 19) on at least two coins; or it's too small to beat a taker's fee + spread at the
  open (needs roughly a 53-54% hit rate at 50c); or the timestamp alignment of the 1-minute Coinbase candles vs Binance
  1-second data can't be pinned down (then the signal could be an artefact).
- **Infrastructure note (before testing):** live, the recorder has Coinbase/Kraken/Bitstamp (all USD) but no Binance;
  a live version would need a USDT feed (OKX or Binance) recorded. Research first; report if it works.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-10 | `research/premium.py`: Coinbase 1-min closes vs Binance 1 s; alignment check; at every window open, premium deviation from its 24 h mean (dev24) and change over 15/60 min (d15/d60) vs the next 15-min Binance return in trailing-vol units, halves A/B | research | Alignment clean: 1-min returns corr 0.98-0.99 at lag 0, ~0 at +-1 min (no lookahead). Median premium -6 bp (USD vs USDT), sd of d60 1.3-1.9 bp. **Every feature positive in both halves on all coins**, but small: d15 corr +0.036/+0.026 BTC, +0.025/+0.021 ETH, +0.019/+0.030 SOL; top-decile hit rate 51.6/54.8, 50.9/53.6, 51.2/52.2%. dev24 and d60 weaker | **Rejected at research.** The sign is real (6/6 coin-halves for d15), but it's worth ~+2c gross per contract at the open vs ~3c of fee + spread. Too weak alone; a candidate input for a combined model. Live use would also need a USDT venue recorded (the recorder's spot feeds are all USD). |

## Learnings
- A widening Coinbase premium predicts the next 15 minutes' move in its direction on BTC, ETH and SOL (corr ~+0.03,
  both halves), too weakly to trade alone at the open.

## Current status
- Stage: **rejected at research.**
