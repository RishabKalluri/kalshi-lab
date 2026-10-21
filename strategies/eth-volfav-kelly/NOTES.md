# ETH VolFavorite Kelly

Markets: KXETH15M. eth-volfav2's code plus a win probability for the sizer (`--sizing kelly:F`); with pct sizing it
trades exactly like v2.

## How the probability is built
- Model P(favourite) = Phi(|Phi^-1(mid)| * ratio): the market's own z-score rescaled by implied/forecast vol.
- That model is ~3x overconfident: at signals it claims ~10c of edge, outcomes give ~3.7c vs mid (Mar-Aug).
- Calibrated P(favourite) = market prob + edge_shrink * (model prob - market prob). edge_shrink is fit in
  vol_fit.py OUT of sample (forecast + threshold on the first 70% of the training data, shrink on the last 30%);
  in-sample it reads 0.85-0.95 because the forecast has seen those markets. Out of sample it is 0.2-0.4 (needs >=200
  held-out signals, else 0 = no Kelly bets).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-21 | calibration screen (dev data Mar-Aug, models fit on earlier months) | research | signals 4,430: market prob 0.789, model 0.889, won 0.826; shrink 0.35 overall, monthly -0.01..0.65 | the model's edge is real but ~1/3 of what it claims |
| 2 | 10-21 | sizing walk-forward Feb-Aug, $1,000 compounding, shrink refit monthly (ad hoc backtests) | sizing | 1%/order +101% (dd 23.3%); kelly 0.25 +251% (dd 14.0%); 0.5 +292% (17.0%); 1.0 +323% (15.7%). Kelly sat out Mar-Apr (too few held-out signals) | Kelly also filters: c/ct 1.8 -> 2.7 |
| 3 | 10-21 | same with shrink fixed at 0.35 (trades every month; mildly optimistic) | sizing | 1%/order +101% (23.3%); kelly 0.25 +290% (14.5%), Apr +$53 vs -$87; 0.5 +326% (22.6%); 1.0 +322% (28.1%) | quarter Kelly best return per drawdown; above half Kelly only risk |
| 4 | 10-21 | live, quarter Kelly, at the user's request (no paper): kelly:0.25, max-frac 5%, bankroll $1,050, max 40/order, 60/market, stop-loss $200; live model fit to Oct 21 (edge_shrink 0.417) | live | started 17:04 UTC | |

## Current status
- Stage: **live** from Oct 21 (replaces v2's 1%/order sizing in tmux live-eth-volfav). Model and edge_shrink refit
  monthly (research/refit_live.py); live reads ~/kalshi-data/models/eth-volfav-kelly/.
- Not validated by the pipeline (sizing isn't part of it) and no paper run: watch the first weeks closely.
