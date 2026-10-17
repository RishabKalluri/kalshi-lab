# Weather bracket fade (wx-bracket-fade)

Markets: KXHIGHNY/LAX/MIA/CHI/AUS (since 2025-10-01), KXHIGHTDAL/TPHX/THOU/TATL/TBOS (since Feb 2026). Development data only (before 2026-08-20); the lockbox was never touched.

## Hypothesis (written before any test)
- Retail overpays for cheap "lottery" brackets relative to what a forecast implies; a taker buying NO (or the forecast-favoured bracket) earns it.
- Wrong if: forecast-implied probability adds nothing over the market price, or the spread + fee eat any longshot bias.

## Data downloaded (free public, in `data/`)
- `fc_<SERIES>.json`: Open-Meteo previous-runs API (`previous-runs-api.open-meteo.com`), hourly `temperature_2m_previous_day1..3`, models ecmwf_ifs025 and gfs_seamless, at the settlement station coordinates (Central Park, LAX, MIA, Midway, Austin-Bergstrom, DFW, PHX, Hobby, ATL, Logan), 2025-09-28..2026-10-13. Forecasts only, no outcomes.
- `obs_<SERIES>.csv`: IEM daily summaries (observed highs), `metar_<SERIES>.csv`: IEM hourly/special METAR temps; both cut at 2026-08-19 (development only).
- Scripts in `research/` (fetch_*.py, build_daily.py, build_snaps.py -> snaps.parquet, model_edge.py, calib*.py, lockin*.py, gbm.py, by_city.py).
- Synthetic quotes follow the engine's backfill book: ask = last taker-buy YES price, bid = last taker-sell YES price.

## Screening results (all research/, no pipeline run; none cleared the bar for one)
1. **NWP forecast vs price.** Day-1 GFS+ECMWF, bias/sd fit on trailing 60 days (forecast sd ~3F vs 2F brackets). Brier 0.140 vs market mid 0.111; logit regression on logit(mid), logit(model): coefs 1.17, 0.04. Taker trades where model beats ask/bid by 3-12c: YES -1.2..-3c/ct, NO -3..-5c/ct, getting worse with the gap. The market already uses better forecasts (NWS/MOS/latest runs).
2. **Longshot bias.** Mid is well calibrated except under 20c: mid 2.8c -> freq 1.4c, 7.4 -> 5.9, 14.9 -> 12.5. Spread is 2-3c though; taker NO on brackets priced under 20c nets -0.5c (by city: -2c..+0.5c). Only bids <=10c (NO cost >=90c) is positive, ~+0.4c per ~98c risked, ~3000 trades in 10 months at 25 ct = a few hundred dollars. Not worth a test.
3. **Intraday lock-in (METAR running max).** 26k market-snapshots were already decided (13 of them with fresh quotes to trade), only 4-8 mis-decided by METAR rounding; dead/locked brackets are not traded at all, so there is nothing to take.
4. **Intraday nowcast ML** (HistGradientBoosting on logit mid, running max vs bracket edges, hour, spread; train Oct-Mar, test Apr-Aug): logloss 0.3693 vs mid 0.3655. No edge over the price.
- KXRAIN: history is only 85 days (from Jul 2026), too short to judge.

## Learnings
- Weather brackets are efficient to anything derivable from free forecasts or observations; takers lose because of spread (mean 2.9c, 2c typical) + fee, which is also why the survey showed negative taker PnL. The money in this category is on the maker side (earn the spread and the <20c longshot bias, no maker fees), which needs real books.
- Quotes in backfill are trade-derived and stale for most brackets (locked ones never trade); fresh-quote opportunities are rare.

## Current status
- Stage: screening only, parked. status `parked`.
- Next step: maker version once the recorder has enough weather books (recording since 2026-10-13): quote cheap brackets (sell YES / buy NO under 20c, post-only), measure fill rates and adverse selection from recorded books; needs ~2-4 weeks of books and the weather book_depth re-measured.
