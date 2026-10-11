# Kalshi Taker Herding

Markets: KXETH15M, KXSOL15M (KXBTC15M as a control).

## Hypothesis (written before any test)
- **Why mispriced:** on thin books, a burst of one-sided Kalshi taker buying (many YES-takers, or many NO-takers,
  within a few minutes) walks the price further than spot justifies: retail chases the move on the Kalshi screen,
  and quoters widen or step back rather than lean against it. The price then drifts back toward the spot-implied
  value. So net signed taker volume over the last few minutes, *net of the spot move over the same minutes*,
  should predict outcome minus price with a negative sign (fade the herd).
- **Who is on the other side:** chasing retail takers paying spread + fee to join a move already in the price.
- **Different from earlier dead ends:** settle-lockin H2 tested single large prints (top 1% size); btc-flowrev H1 tested
  the unexplained Kalshi *price* move on BTC only. This tests aggregate *flow* imbalance on the thinner coins.
- **What proves it wrong:** signed taker flow (raw and residual to the spot move) doesn't predict y - mid with a
  consistent sign in both halves (A: Dec-Apr, B: May-Aug 19); or the extreme decile (fade or follow) isn't positive
  at the next real fill after the fee in both halves on ETH or SOL.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-10 | `research/screen.py`: net Kalshi taker imbalance over (t-W, t] at every dataset checkpoint (mid 15-85c, >=3 trades), W = 60/180/600 s; corr with y - mid; fade PnL at next real fill after fee by |imb| quintile, halves A/B | research | corr(imb, y - mid) between -0.019 and +0.005 everywhere. Fade PnL by quintile -0.2..-2.8c (the fee + spread baseline) on all three coins and both halves, no quintile positive; |imb| > 0.8 with >= 8 trades: -0.3..-5.7c. Following is the mirror minus costs, also negative | **Rejected at research.** Kalshi taker flow carries no information beyond the price, in either direction, at any window. Together with settle-lockin H2 (big prints) and btc-flowrev H1 (unexplained price moves), Kalshi's own trade tape looks fully priced. |

## Learnings
- Kalshi's own taker-flow imbalance (1-10 minutes) predicts nothing on BTC, ETH or SOL; the tape is priced.

## Current status
- Stage: **rejected at research.**
