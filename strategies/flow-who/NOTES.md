# Flow-Who

Markets: KXBTC15M, KXETH15M, KXSOL15M. Status: rejected at research (no pipeline run, no budget used).

## Hypothesis (written before any test)
- Why mispriced: forced flow (a few huge perp prints, perp leading spot, one-sided bursts) overshoots and reverts before
  settlement; broad informed flow persists; Kalshi prices both the same, so the favourite is overpriced after forced
  moves and underpriced after informed ones.
- Other side: takers pricing the favourite off the price move only.
- Wrong if: the flow split doesn't separate reverting from persisting at the next real Kalshi fill after fees.

## Research (development data < 2026-08-20; research/*.py; earlier OOM run's screen.py replaced by screen2.py, month-by-month)
- **H1 in-window classification** (screen2.py, an2.py, reg2.py): rows = market x horizon (60..840 s before close) where
  |z| > 1.5 (move since open in units of 1h-trailing 1s sigma); features from OKX perp + Binance spot flow up to t-1
  (perp/spot imbalance, last-third imbalance, largest print share, mean trade size, volume and trade count vs 1h baseline,
  perp share, perp-minus-spot return lead, jumpiness). Following the move at the next real fill after fees: ETH -0.03c,
  SOL +1.08c, BTC -0.84c; fading is -3.4..-4.9c everywhere. Quintile splits flip sign between Dec-Apr and May-Aug for
  nearly every feature. Clustered regression of follow edge at mid on feature ranks: only spot imbalance is positive in both
  halves (+1.8c over its full range, t 2.6) and volume/trade-count terms flip sign. Moves persist ~2.6c at mid (ETH), which
  the spread and fee eat.
- **H2 30 s shock event study** (shock2.py): |z30|>3 with perp volume >3x its 6h median, 300 s cooldown, ~1.2-2k events/month/coin.
  No reversal at any horizon: continuation of +0.07..+0.17 sigma at 60 s, decaying to ~0 by 600 s, strongest when the perp
  led spot (top tercile of lead: +0.29..+0.33 sigma at 60 s, BTC still +0.17 at 600 s). Largest-print share and one-sidedness
  barely matter ("forced" does not revert). evfill.py: following the shock at the next real Kalshi fill 1-11 s later, held to
  settlement, after fees: ETH -2.83c, SOL -0.31c, BTC -1.24c (7k / 3k / 9k events with both-side fills); no tercile of any
  feature positive for ETH or BTC; SOL terciles noisy (+-2c, n ~1k).
- **H3 walk-forward GBM on all flow features** (gbm.py; expanding fit by month, trade the top predicted follow edge):
  out-of-sample corr 0.026; top 5-20% by prediction +0.4..+0.85c per row but -0.5..-1.0c per market, se 0.5-1.0.
- **H4 perp-lead continuation** = the top "lead" tercile in H2: gross edge exists in spot (spot catches up to the perp) but
  Kalshi has repriced by the first real fill (BTC top-lead tercile -1.4c, ETH -1.8c, SOL +0.3c).

## Learnings
- Big moves in these markets continue slightly rather than revert, and Kalshi prices that about right; spread + fee
  (~3-4c round trip at taker fills) swallow the residual. Flow adds almost no information about continuation beyond
  the move itself (R2 gain tiny), and the sign of any flow effect is unstable across halves.
- Kalshi taker fills 1-11 s after a spot shock already include the spot move (consistent with btc-lead).
- Memory: dense per-second flow for 9 months crashed the first run; process per month (screen2.py) and stream Kalshi
  market files per day (evfill.py loads 11-14 GB if all trades are kept in lists).

## Current status
- Rejected at research. Nothing tradable: edge per trade is below costs in every split. Paper/live would also have needed
  a live flow stream.
