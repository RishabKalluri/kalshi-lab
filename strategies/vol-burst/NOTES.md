# Vol Burst (and other volatility screens)

Markets: KXETH15M, KXSOL15M (screened on development data only, closes before 2026-08-20).

Request: "a strat based on volatility or something; eth-volfav is our most successful one". The volfav family's
lockbox is spent on SOL (sol-vomma failed) and BTC prices vol correctly, so I looked for *different* volatility
mechanisms first. All screens: side PnL at the **next real taker fill** (next same-side trade within 10 s) after the
Kalshi taker fee, split Dec–Apr (A) vs May–Aug (B), h 60–840 s. Scripts in `research/`.

## Hypothesis H1 (written before any test): vol-burst underdog
- **Why mispriced:** spot vol clusters at minute horizons. When rv over the last 5 min jumps well above the last
  hour's, the rest of the window will be more volatile than Kalshi quoters (anchored on the calm stretch) price,
  so implied vol is too low and the 10–45c underdog is cheap. Opposite side and regime to eth-volfav.
- **Who loses:** favourite buyers late in a newly volatile window; slow quoters.
- **Wrong if:** the top burst bucket's underdog PnL at the next fill after fees is <= 0 in either half.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-10 | **H1** `research/screen.py`: underdog/favourite PnL by deciles of rv_5m/rv_60m, rv_5m/rv_15m, iv/rv_5m | research | Underdog negative in **every** decile on ETH and SOL (top burst decile ETH −3.2/−2.1c, SOL −3.8/−1.3c); low-iv deciles not positive in both halves | **H1 rejected.** A starting vol burst doesn't make the underdog cheap: quoters widen fast enough. |
| 2 | 10-10 | **H2** `research/fv_screen.py`: a vol forecast that knows the clock (NY hour-of-week × quarter-hour × h, rv_5m) vs volfav's HAR; logistic-calibrated fair prob from spot distance; trade either side when model edge > cost | research | Clock model improves OOS R² of log rv_fut 0.609 → 0.631 (ETH), but realized PnL is negative in every model-edge bucket except +0.1..+0.2c in B only at edge > 6c; market log loss 0.3631 beats the model's 0.3668. Market + model combined (H2b): still ≤ 0 in A everywhere | **H2 rejected.** A better vol forecast alone doesn't beat the market net of taker costs; the market already prices the clock. |
| 3 | 10-10 | **H3** `research/spot_feats.py` + `jump_skew.py`: bipower variation / jump share (HAR-CJ, Andersen–Bollerslev–Diebold 2007): jump-driven trailing vol should be less persistent, so the favourite is cheaper after jumps | research | Jump terms add +0.002 OOS R² (ETH 0.6087 → 0.6103, SOL 0.615 → 0.617). eth-volfav-signal favourites by jump quintile: ETH high-jump −1.0/+1.5c and −0.9/+1.8c (A/B disagree); SOL consistent (+1.4/+2.0, +3.5/+1.4) but SOL's volfav-family lockbox is spent | **H3 rejected** on ETH (halves disagree); not testable on SOL. |
| 4 | 10-10 | **H4** realized skewness (15m/60m), signed largest jump, 15m/60m return vs future move in σ units | research | All \|corr\| < 0.02, signs flip between halves; side PnL by skew decile has no cell positive in both halves on both coins | **H4 rejected.** No directional information in realized skew at this horizon. |
| 5 | 10-10 | **H5** deep favourites 80–97c by h × band × calm/hot (`research/deepfav.py`, ETH/SOL/BTC) | research | Almost every cell negative; scattered +0.1..+0.9c cells don't repeat across halves or coins | **H5 rejected.** No late favourite bias even in calm regimes. |
| 6 | 10-10 | **H6** `research/maker_fav.py`, `maker_fav2.py`: eth-volfav's signal executed as a maker one tick above the favourite's bid | research | ETH signal rows: +2.9 / +2.3 / +4.2c per filled contract (Dec–Apr / May–Jun / Jul–Aug) vs taker +0.8 / +0.6 / +2.9c; fill ~45–60% after April. Non-signal maker rows lose (−1..−1.7c) | Promising → moved to its own folder **`strategies/volfav-maker/`** (derived_from eth-volfav). |

## Learnings
- **Kalshi ETH/SOL quoters react to vol bursts quickly**; the underdog is never cheap after a burst (H1).
- **The deterministic vol clock (NY hours, quarter-hour, in-window decay) improves forecasts but is already priced** (H2).
  A pure model-vs-market fair value loses at the next real fill on both sides; only selective signals (eth-volfav's
  top-30% iv/forecast) clear taker costs, and barely.
- **Jumps vs continuous vol barely matter for 15-minute forecasts** (+0.002 R²) (H3); realized skew is noise (H4).
- **Execution, not the forecast, is the main lever left for volfav-type signals:** the taker gives away ~3–5c to fee +
  spread; a maker on the same signal keeps most of it in screens (H6). Engine results pending (see volfav-maker).

## Current status
- Stage: **rejected at research** (H1–H5). H6 continues in `strategies/volfav-maker/`.
- Budgets untouched (0/3 full, lockbox unused).
