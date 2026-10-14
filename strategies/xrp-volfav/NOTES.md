# XRP VolFavorite

Markets: KXXRP15M (Kalshi 15-minute XRP up/down; same 60s-average CF Benchmarks settlement as ETH).

Port of `eth-volfav2` (strategy.py and vol_fit.py copied unchanged; see eth-volfav/NOTES.md for how it works).
Requested by the user to expand VolFavorite to other markets; XRP and DOGE were the best candidates in the Oct 12
expansion survey (volume, history since Feb 11 / Mar 19).

## Hypothesis (written before any test)
ETH's 15-minute market overprices short-horizon vol and the BTC market does not; the difference looks like efficiency (thinner, more retail markets misprice more). XRP's 15-minute market is smaller and more retail than ETH's, so the same overpricing should appear. The other side: traders paying up for the trailing side late in the window. Wrong if the walk-forward on XRP is flat or negative, or the edge appears only in one or two months.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-13 | port of eth-volfav2; fit filter rv_fut > 0.05 ($, ETH-scaled) made price-relative (2e-5·S) | fit | first fit empty at XRP's ~$1.30; refit betas 0.49/0.18/0.23, threshold 1.27 (ETH 0.50/0.13/0.18, 1.42) | absolute $ thresholds don't port across coins |
| 2 | 10-13 | smoke + quick | quick | smoke +12.7¢/ct (9 mkts); quick +5.9¢/ct (74 mkts, CI −2.6..+12.9) | passed |
| 3 | 10-13 | full walk-forward Apr–Aug 19 (monthly refit) | full | **promising**: pooled +1.33¢/ct, CI +0.45..+2.24, 4,206 markets; months −0.05/+2.87/−1.05/+2.23/+2.12; 2× latency +0.42 (CI −1.24..+2.05) | weaker than ETH (+2.16, 6/8 months); May carries much of it; latency-sensitive |
| 4 | 10-13 | lockbox Aug 20–Oct 12 (one shot) | lockbox | **strong pass**: +1.45¢/ct, CI +0.04..+2.73, 2,277 markets; Aug +1.26, Sep +1.72, Oct +0.86; 36/54 days positive | the edge holds out of sample on XRP, at about 2/3 of ETH's size |
| 5 | 10-13 | live model refit on all data to Oct 13 (22,894 markets, threshold 1.259); paper at rv_scale=1.05, slip_c=1, 0.5%/order | paper | started | rv_scale not measured for XRP yet (ETH 1.02, SOL 1.11): re-measure from a week of recorded spot |
| 6 | 10-14 | monthly refit routine (as eth-volfav2) | refit | first refit = yesterday's fit (22,894 markets, threshold 1.259) | |

## Current status
- Model: refit monthly (1st, UTC) by research/refit_live.py; live/paper read ~/kalshi-data/models/xrp-volfav/ (params/ is the fallback and the backtest model).
- Stage: **paper** since Oct 13 (rv_scale=1.05, slip_c=1, 0.5%/order). Family: eth-volfav; this market's lockbox is spent (strong pass).
- Next: ~2 weeks of paper; re-measure rv_scale from recorded XRP spot (kalshi-recorder-alts) after a week; measure real book depth (config's 13 is a placeholder). Live only with the user's OK.
