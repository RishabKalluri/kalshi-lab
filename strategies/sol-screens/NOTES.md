# SOL screens (research only)

Agent run 20261016-0046-2, brief "KXSOL15M: your choice of idea". No strategy.py was written: every screen was clearly negative.
Scripts are in `research/` (they read `research/data/KXSOL15M.parquet`, dev data only; fills = next real taker trade within 10 s, unrounded fee 0.07P(1-P); halves split at 2026-05-01).

## Screens (all rejected)
| # | idea | result |
|---|------|--------|
| 1 | multi-hour trend (30 min .. 8 h strike-to-strike z) reversal/continuation at the open; hourly/4h/00 UTC boundary variants | only the known last-window (z1) reversal; z2 adds nothing given |z1|<1; boundary variants sign-flip between halves (`trend.py`, `z2.py`, `bd.py`) |
| 2 | walk-forward logistic on z1..z16, D/sigma, vol ratio, clock at h=840 | Brier 0.2308 vs market 0.2302; net -1..0c, 2/4 months (`wf.py`) |
| 3 | Kalshi mid changes not explained by spot (5 horizon pairs), fade | every extreme quintile loses 1-4c (`mv.py`) |
| 4 | BTC/ETH realized vol in SOL's HAR | OOS R2 0.6887 -> 0.6879/0.6885 (`xv.py`); Kalshi n_trades (own/previous windows) 0.6915 -> 0.6923 (`nt.py`) |
| 5 | basket filter (SOL reversal only when BTC/ETH moved too) | SOL-only moves rare (13-70/half), mixed; basket moves = ordinary reversal (`bk.py`) |
| 6 | CF-vs-Binance basis deviation as drift predictor | corr with outcome -0.003; deciles flat (`bas.py`) |
| 7 | in-window momentum/mean-reversion slope of future move on D/sigma, h 60..840 | |slope| <= 0.03 for h<=600 (`sl.py`) |
| 8 | price-band calibration of takers' fills | underdogs 20-50c lose 3-4c net, 70-95c favourites ~0..+0.5c, nothing past costs (`cal.py`) |
| 9 | pooled 5-coin HistGradientBoosting (21 features incl. trend z, vol ratios, iv/rv, clock, staleness), monthly walk-forward, 715k rows | Brier 0.11800 vs mid 0.11845; net -0.19..+0.45c, 2-3/5 months positive at any threshold (`gbm.py`) |

## Learnings
- **The open-reversal edge has largely decayed on every coin.** z1 (|z|>1.25) fade, all five coins, by half: Jan-Apr +4.8c/+4.3c (buy-YES / buy-NO side), May-Aug +1.9c / -0.8c. By month the NO side (fade pumps) is -2.6c in Jun, -2.4c Jul. SOL is the last holdout (+3.3c after ups, n=493, May-Aug). This agrees with sol-midrev's weak lockbox (+2.1c, Sep -1.0c). Only 06-09 UTC stays positive in both halves, and that is a post-hoc slice.
- Spot-derived taker edges look mined out: vol forecast is saturated (HAR R2 0.69, nothing adds), pooled GBM finds nothing, Kalshi price moves are efficient.
- Remaining sources: market-maker side (queue-aware quoting needs recorded books, development data from Nov 1), cross-venue (Polymarket) and ladder data (KXSOLD absent; KXETHD/KXBTCD are 1-market/day samples).

## Status
rejected (research). Next: maker quoting on books after Nov 1.
