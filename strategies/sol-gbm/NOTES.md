# sol-gbm (research only, rejected)
- H1 wf.py: monthly walk-forward HistGradientBoosting on 15 features (z, logit mid, spread, vol ratios, hour, dow, ages, trades): Brier 0.1174 vs market 0.1180; first signal per market at next real fill, edge threshold 2-10c: net -0.5..-1.2c buy, -1.1..+0.3 sell (noise).
- H2 perp_lead.py / perp_kalshi.py / perp_an.py: OKX perp-vs-Binance spot deviation predicts spot return (corr 0.16 at 10 s, 0.10 at 30 s, 0.05 at 2 min, both halves) but Kalshi's next fill already prices it: net -0.4..-1.6c in 2nd half, corr with y-mid 0.06 at h=60 s.
- H3 basis.py: perp-spot basis level/change, perp taker imbalance and volume ratio at the open vs next-window move/vol/y-mid: |corr| <= 0.05, unstable.
