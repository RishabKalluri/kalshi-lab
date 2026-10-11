# Top-of-Hour Calm Favourite

Markets: KXBTC15M, KXETH15M, KXSOL15M (one rule, all three coins).

Came out of `strategies/bell-vol/` screen 1 (other exchanges' opens, rejected): on every clock the window starting on
the hour had lower implied-vs-realized vol than its neighbours, which pointed at a minute-of-hour cycle rather than at
any exchange's bell.

## Hypothesis (written after bell-vol screen 1, before any screen in this folder)
- **Why mispriced:** crypto vol has a minute-of-hour cycle (hourly candles, hourly TWAP/rebalancing schedules,
  hourly options/ladder expiries all fire at :00). The window starting at :00 should be the most volatile of the
  hour and the one ending at :00 (starting :45) the calmest. Kalshi prices every quarter-hour window off the same
  trailing vol, so it overprices the remaining move in the :45 window (favourite cheap) and underprices it in the
  :00 window (underdog cheap).
- **Who is on the other side:** underdog buyers and quoting bots using trailing vol with no minute-of-hour prior.
- **What proves it wrong:** realized vol isn't lower in :45 windows (and higher in :00); log(iv/rv_fut) doesn't rise
  from :00 to :45; or the favourite in :45 windows (underdog in :00) isn't positive at the next real fill after the
  fee in both halves (A: Dec-Apr, B: May-Aug 19) on at least two coins; or per-month results are mostly negative.

## Strategy v1 (fixed after screens 1-3, before any backtest)
`HourCalmFavourite`: windows starting at :45 (UTC minute, i.e. closing on the hour), every day, BTC+ETH+SOL. At
checkpoints h = 720/600/480/360 s, the first where the favourite's mid is 65-90c: buy the favourite at the touch, IOC,
hold. The 65c floor was chosen after seeing screen 3 (55-65c ~0, 65-90c +1..+3.6c) but has a reason independent of
it: a binary's sensitivity to vol (-phi(d)*d) is zero at 50c and peaks near 84c, so overpriced vol barely moves a 55c
favourite, while the taker fee is highest there.

## Ideas and prior work used
- `strategies/us-hours-vol/` (vol runs on a clock; the market misses the 9:30 ET step), `strategies/asym-vol/` (vol
  decays across every 15-min window, ~2x in the first 10 s), `strategies/eth-volfav/` (favourite cheap when vol is
  overpriced; HAR forecast). This idea is a clock effect at the hour level, on all three coins including BTC.

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-10 | `research/hour_start.py`: by window start minute (:00/:15/:30/:45; 9:30 and 10:00 ET weekday windows excluded), vol vs month mean, log(iv/rv_fut), underdog/favourite PnL at next real fill after fee, by horizon band, halves A/B | research | Monotone in the start minute on all three coins and both halves: favourite PnL :00 -2.4, :15 -2.4, :30 +0.5, :45 **+1.9/+1.1c** (ETH h 600-840; BTC +1.0/+2.3, SOL +2.3/+0.5); underdog the mirror (but never positive at :00). log(iv/rv_fut) highest at :45 (ETH 0.18 vs 0.13 at :00) | The :45 window's favourite is the tradable side; the :00 underdog isn't (fee + spread eat it). |
| 2 | 10-10 | `research/minute_vol.py`: mean squared 1-min return by minute of hour relative to its hour (Binance 1 s, Dec 10 - Aug 18) | research | Each quarter-hour starts with a burst and decays (minute :00/:30 1.3-1.6x, minutes 56-59 ~0.6x); quarter :45->:00 is 0.85-0.90x the hour's variance, :00->:15 1.09-1.12x; same on BTC, ETH, SOL and both halves | Vol fact confirmed: the last quarter of the hour is the calmest, ~12% less vol than the first. |
| 3 | 10-10 | `research/fav_by_quarter.py`: one trade per market, first checkpoint h 240-720 with favourite mid 55-90c, at next real fill after fee | research | :45 windows ETH +1.12/+0.35 (se 0.9), SOL +1.11/-0.12, BTC +1.41/+2.41 (**BTC 9/9 months positive**); :00/:15 windows -1..-5c. Within :45: entry h=720 best (+1.3/+1.3/+2.8), fav 55-65c ~0 (-0.0/-1.4/+0.9), 65-75c +1.6/+1.4/+3.6, 75-90c +1.1/+2.1/+1.5 | ~15k markets in development: the sample problem that stalled us-hours-vol doesn't apply. Even BTC (efficient everywhere else) has it. |

| 4 | 10-10 | v1, ad-hoc BTC Jun 1-8 | ad-hoc | +1.2c/ct, 130 of 168 :45 windows traded | mechanics as intended |
| 5 | 10-10 | v1 smoke; quick (job hour-calm-1010-190255) | smoke/quick | smoke passed (14 markets); quick passed: +3.82c/ct, CI -2.0..+9.4, 178 markets, 4/4 days | |
| 6 | 10-10 | v1 (job hour-calm-1010-190411) | **full (1/3): inconclusive** | **+0.62c/ct, CI -0.11..+1.40**, 158k contracts, 12,311 markets, 5/8 months (Jan -1.2, Feb +1.2, Mar -0.5, Apr +0.1, May +0.5, Jun -1.4, Jul +0.8, Aug +4.9); 2x latency Jun-Aug +1.42c (CI +0.15..+2.64). By coin BTC +1.17, ETH +0.61, SOL -0.03. **By entry checkpoint: h=720 +2.23c (4,874 markets), 600 -0.15, 480 -0.06, 360 -1.82.** Weekends +2.19c, weekdays -0.03c | Half the research figure, and all of it in the first checkpoint. Reading: at h=720 the market's trailing vol still contains the burst that opens every quarter-hour (minute_vol.py: first minutes 1.2-1.6x), so it overstates the calm remainder most; at later checkpoints trailing vol has caught up and the fallback entries are markets that moved late (adverse). Screen 3 had already shown h=720 as the best fixed horizon on all three coins. **One change for v2: enter only at h=720.** (Weekend strength noted, deliberately not filtered.) |

| 7 | 10-10 | v2 smoke; quick (job hour-calm-1010-194936) | smoke/quick | smoke passed (8 markets); quick passed: +9.83c/ct, CI +1.4..+17.3, 79 markets | |
| 8 | 10-10 | v2 (job hour-calm-1010-195103) | **full (2/3): promising** | **+2.17c/ct, CI +1.06..+3.36**, 67k contracts, 4,874 markets, **7/8 months** (Jan +1.3, Feb +2.5, Mar -0.2, Apr +0.6, May +1.8, Jun +1.4, Jul +3.7, Aug +6.7); 2x latency Jun-Aug +3.53c (CI +1.56..+5.36) | Caveat: these are exactly v1's h=720 entries, picked after seeing v1's breakdown on the same data, so this full confirms the selection rather than testing it. The lockbox is the real test. |
| 9 | 10-10 | v2 (job hour-calm-1010-212015) | **lockbox: FAIL** | **-1.21c/ct, CI -3.60..+1.26**, 15.4k contracts, 1,327 markets, 23/52 days; Aug 20-31 -0.56, Sep -1.35, Oct 1-10 -1.61, recorded books -1.57. By coin BTC -3.3, ETH +0.3, SOL -0.5; weekends -4.0, weekdays -0.2 | **Rejected.** The strongest development slices (BTC, weekends) reversed hardest. The vol cycle is real, but the favourite's underpricing in the :45 window didn't hold out of sample. |

## Learnings
- **A post-hoc subset of an inconclusive full test is not new evidence.** v1 (all checkpoints) was +0.62c; keeping the
  best checkpoint gave a "promising" +2.17c on the same trades, and the lockbox lost -1.2c. Next time, treat a
  subset found in a full test's breakdown as a hypothesis for *new* data, and be sceptical of an edge that lives in
  one slice of the breakdown.
- **Crypto vol has a minute-of-hour cycle** on BTC, ETH and SOL: each quarter-hour opens with a burst (first minute
  1.3-1.6x) and decays to ~0.6x in its last minutes, and the quarter before the top of the hour (:45 -> :00) is the
  calmest of the hour (~12% less vol than :00 -> :15).
- The favourite in the window that closes on the hour is underpriced, more on weekends, and only early in the window
  (3 minutes in); by 5+ minutes in, the market's trailing vol has caught up.

## Current status
- Stage: **rejected at the lockbox** (one shot spent; no retry). Full budget used: 2 of 3.
- Side screen while the full ran: `research/open_edge.py` (previously BTC only) on ETH/SOL. The market beats a
  spot-vs-strike model in the first minute after the open and the combination adds <=0.001 Brier; not slow at the
  open on the thinner coins either.
