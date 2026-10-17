# VolMirror (derived_from volfav-pool)

## Hypothesis (before testing)
Mirror of VolFavorite: when Kalshi's implied vol is far below a HAR forecast, the market is under-pricing vol, so cheap
underdogs (<30c) are underpriced late in the window. Wrong if full isn't promising or the edge is gone against book depth.

## Research (research/s1.py, dev data, walk-forward HAR per coin)
- Underdog net PnL vs ratio quantile (all 5 coins, h 60-840): monotone, -5.3c (top 5%) to -0.5c (bottom 5%). Level ~0 overall.
- Positive cell: bottom 5%, underdog <30c, h 120-240: +1.64c (se .54, 5245 obs, 6/8 months). h 300-480 / 600-840: ~0 (cells chosen after looking: weak evidence).
- Cross-coin ratio adds nothing to own ratio (H2 in report).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-15 | v1 rule | smoke | ok | folder + params/ need group lab, g+w for the worker |
| 2 | 10-15 | v1 | quick | passed, 50 mkts, -0.38c, CI -10.7..+11.2 | too few trades to say |
| 3 | 10-15 | v1 | full job volmirror-1015-160940 | running | |
