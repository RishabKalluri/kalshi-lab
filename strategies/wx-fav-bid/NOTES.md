# Weather favourite bid (wx-fav-bid)

Agent run 20261017-0100-1. derived_from wx-maker (same markets, but it only quoted brackets with mid 5-50c, so never the favourite).

## Hypothesis (before any engine run on the full period; one 2-week NY look, Mar 10-24, to check it trades: -36 on 767 contracts, noise)
KXHIGH ladders are too wide early in the day. Screens (strategies/mention-no/research/wx_calib.py, wx_askbid.py, trade-proxy ask/bid,
10 cities, 335 dev days): event price sum 1.04; implied variance 4.25 vs realized squared error 3.12 at 24 h (ratio 0.63-0.93 in every
city); the rank-1 bracket wins +3.54c more often than its mid at 24 h (se 0.95; 30 h +2.1, 18 h +2.2, 12 h -0.6), ranks 2-4 are overpriced
by 1.4-2.5c. Taker: buy favourite at the ask +0.53c net (24 h), sell rank>=4 at the bid +0.4..+1.0c net: too small. Maker: no fee, and
joins the bid. Counterparty: retail spreading across brackets / pricing from the NWS point forecast without the sharpness of the nowcast.
Wrong if: fills are adversely selected (wx-maker's bids lost ~3c) -> pooled CI of PnL per city-day <= 0.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-17 | v1: bid on the modal bracket 12-34 h before close, touch, qty 10, cap 30/bracket; ad hoc books runs, 10 cities x 14-day chunks Jan 7 - Aug 31 | ad hoc (no pipeline) | 1,979 city-days, 106k contracts, **-0.33c/ct** (CI -1.44..+0.88), months +/-; by fill time-to-close: <20h -3.35c, 20-26 +0.9, 26-30 +0.3, 30-34 +2.1 | edge fades as the close nears (matches the fixed-time screen); late fills are adversely selected |
| 2 | 10-17 | v2: window 26-40 h; sides=both (also offer ranks 2-3 with mid >= 10c) | ad hoc | favourite bid **+0.70c/ct** (CI -1.18..+2.82, 1,845 city-days, 71k contracts, 4/8 months); neighbour offers **-1.11c/ct** (CI -1.96..-0.26, 134k contracts) | the ladder is wide in the mid but the neighbour asks get picked off; window chosen from v1's dev fills (post hoc) |

## Learnings
- KXHIGH ladders are too wide early (implied var 1.4x realized; favourite +3.5c underpriced at mid at 24 h), but harvesting it with touch-joining quotes
  nets +0.7c/ct (CI includes 0) after adverse selection, and offering the neighbours loses 1.1c/ct. Taker versions net <= +0.5c at proxies.
- Power: favourite-bid city-day pnl needs ~5-10k city-days to show +1c; the pipeline's books source only fits 1-2 cities in sandbox memory, so no
  full test was run (a 1-city full cannot reach a CI above 0 at this edge size).

## Current status
- parked at ad hoc (no pipeline budget used). Revisit if the books source gets lighter (multi-city) or with a sharper favourite filter
  (e.g. lead over rank 2, forecast agreement) chosen from dev screens.
