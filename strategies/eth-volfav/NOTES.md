# ETH VolFavorite

Markets: KXETH15M (Kalshi 15-minute ETH up/down; YES if the 60s average of CF Benchmarks ETH RTI before close
is at least the 60s average before open).

## Hypothesis (written before testing)
- **Why mispriced:** ETH's 15-minute market overprices short-horizon volatility, especially after volatile
  stretches, so late in the window the side that's currently winning is cheaper than its true probability.
- **Who's on the other side:** takers paying up for reversals (lottery-ticket buyers of the underdog) and makers
  pricing vol off recent moves.
- **Proved wrong if:** walk-forward months are mostly negative, or the identical test works on BTC (that would
  point to a method artifact rather than an ETH-specific inefficiency).

## How it works
At 7 fixed checkpoints (T-360, 300, 240, 180, 120, 90, 60 s), if the market isn't near 50/50 or decided:
1. distance D = spot + basis − strike (basis = strike − our 60s spot average before open),
2. implied vol iv = D / (Φ⁻¹(mid) · √(τ − 40)) (the −40 s accounts for the 60s settlement average),
3. forecast vol = HAR model on trailing 15m / 1h / 4h realized vol + UTC hour + horizon (`vol_fit.py`),
4. if iv / forecast > the 70th-percentile threshold (fit on training data), buy the favorite at the ask (IOC).
`fit()` refits the model before every walk-forward month on earlier data only (`params/` holds the fits).

## Ideas and prior work used
- Started from "implied vs realized vol" research (`research/vol_analysis.py`, `research/vol_edge.py`).
- The BTC version of the same idea failed (BTC prices vol correctly) - see `strategies/_archive/registry.json`.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 09-30 | research: vol-ratio buckets on 30 days | research | test half +4.2¢/ct, CI +1.7..+6.5; BTC control −2.1¢ | effect is ETH-specific |
| 2 | 09-30 | engine, entries every second, model on Sep only | full (15 days) | +$384, +1.6¢, t=1.29 | not significant |
| 3 | 09-30 | 12-month data, research walk-forward | research | +2.2¢ (70th pct), CI +1.1..+3.4, 6/8 months | holds across the year |
| 4 | 09-30 | engine walk-forward, every-second entries | full | **−0.16¢**, CI −1.2..+0.8 | research ≠ engine |
| 5 | 09-30 | **fixed checkpoints** instead of first crossing | full (Apr/Jul/Sep) | −0.2 / +8.2 / +2.4¢ | entering on the first second the signal crosses buys momentary spikes that reverse |
| 6 | 09-30 | pipeline walk-forward, monthly refits | full | promising: +2.13¢, CI +0.6..+3.6, 5/8 months | |
| 7 | 09-30 | realistic backfill depth (43), August refilled | full | **promising: +2.16¢, CI +0.93..+3.45, 6/8 months, +3.0¢ at 2× latency** | backtests had traded ~2.7× smaller than live |
| 8 | 10-01 | sizing 1% → 0.5%/order | — | worst drawdown 26% → ~13% | size for drawdown, not return |

## Learnings
- **Entry timing can flip the sign.** Evaluate at fixed times; "first moment the signal crosses" is adverse selection.
- **Research scripts simplify execution;** only engine results count (iteration 3 vs 4).
- **Backfill has trades but no books;** the last trade's size understates depth ~5×. Use `MARKETS[...].book_depth`.
- **Paper can't prove an edge quickly** (~1/3 chance a real +2¢ edge looks negative after a week). Paper checks execution.
- **Thinner markets are less efficient:** BTC no edge, ETH edge. Try SOL and smaller coins next.
- The edge is concentrated outside US afternoon hours (13-16 UTC trade half as often).

## Current status
- Stage: **paper trading** (since Sep 30, 0.5%/order, `deploy/paper/eth-volfav.json`).
- Lockbox: **spent**. It was developed on data through Sep 29 before the lockbox existed; paper is its out-of-sample test.
- Next: ~1 week of paper (~100 markets), compare per-contract results and fills to the walk-forward, then the $200 live-trial decision.
