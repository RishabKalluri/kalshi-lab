# Exchange-Open Vol Steps

Markets: KXETH15M, KXSOL15M, KXBTC15M (screening all three; the strategy's series are chosen before the pipeline).

Builds on `strategies/us-hours-vol/` (derived_from): there the 9:30 ET equity bell is the one scheduled vol step-up
the Kalshi price misses (+4.3c/ct at full, sample-limited to one window per coin per US trading day). Its slot scans
were all done on the **New York clock**. Bells of exchanges that keep a different clock were therefore smeared over
two NY slots for most of the year and never tested on their own clock.

## Hypothesis 1 (written before any test): the other equity opens are vol steps the market misses too
- **Why mispriced:** Tokyo (09:00 JST = 00:00 UTC, no DST), Shanghai/Hong Kong (09:30 local = 01:30 UTC, no DST) and
  London/Frankfurt (08:00 London = 07:00 or 08:00 UTC, UK DST) open at fixed local times. If crypto vol steps up at
  those opens the way it does at 9:30 ET, a Kalshi quoter pricing the window off calm pre-open trailing vol under-
  prices the move, and the underdog is cheap in the window that starts at the open.
- **Who is on the other side:** favourite buyers and quoting bots using trailing realized vol without a clock prior
  (the same population that misses the 9:30 ET bell).
- **What proves it wrong:** (1) no vol step at those opens on their own clock (or the London step doesn't follow UK
  DST); (2) log(iv/rv_fut) in the open window isn't below the typical level; (3) the underdog at the next real fill
  after the fee isn't positive in both halves (A: Dec-Apr, B: May-Aug 19) on at least two coins; (4) the same-clock
  weekend/holiday placebo shows the same thing (then it isn't the bell).

## Hypothesis 2 (written after screen 1 showed lower iv/rv in :00-start windows on every clock, before screen 2)
- **Why mispriced:** crypto vol has a minute-of-hour cycle (hourly candles, hourly TWAP/rebalancing schedules,
  hourly options/ladder expiries all fire at :00). The window starting at :00 should be the most volatile of the
  hour and the one ending at :00 (starting :45) the calmest. Kalshi prices every quarter-hour window off the same
  trailing vol, so it overprices the remaining move in the :45 window (favourite cheap) and underprices it in the
  :00 window (underdog cheap).
- **Who is on the other side:** underdog buyers and quoting bots using trailing vol with no minute-of-hour prior.
- **What proves it wrong:** realized vol isn't lower in :45 windows (and higher in :00); log(iv/rv_fut) doesn't
  rise from :00 to :45; or the favourite in :45 windows (underdog in :00) isn't positive at the next real fill after
  the fee in both halves on at least two coins; or per-month results are mostly negative.

## Ideas and prior work used
- `strategies/us-hours-vol/` (NOTES, `research/iv_gap.py`, `research/open_dog.py`): method and placebo design.
- `strategies/eth-volfav/` implied-vol math (dataset column `iv`), `research/build_dataset.py` dataset.

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-10 | `research/opens.py`: open window and 3 neighbours each side on the exchange's own clock (Tokyo, HK, London; NY as the control), local weekdays vs weekends: vol vs month mean, median log(iv/rv_fut) mid-window, underdog PnL at next real fill after fee, halves A/B | research | **Tokyo 09:00:** vol +0.24 (vs +1.03 at NY 9:30), gap lower (ETH 0.10 vs ~0.30), but underdog flips: ETH +5.2/-10.1, BTC +1.4/-14.7, SOL +4.3/-3.8. **HK 09:30:** no step (+0.28, same as 09:00), underdog ~0. **London 08:00:** no vol step (+0.04); underdog +7.8/+4.0 ETH, +5.0/+6.7 BTC but SOL -9.8/-17.2, so without a vol step it's noise. NY 9:30 control reproduces us-hours-vol | **H1 rejected:** only the New York bell is a big scheduled vol step that Kalshi misses. Side finding: on every clock, windows starting on the hour had lower iv/rv than their neighbours, which is a minute-of-hour effect, not a bell. Followed up in `strategies/hour-calm/`. |

## Learnings
- Crypto vol has a modest step at the Tokyo open (00:00 UTC, +0.24 log vs the month mean) and none at the HK or London
  opens; the New York 9:30 bell (+1.03) is in a class of its own.

## Current status
- Stage: **rejected at research** (H1). The side finding moved to `strategies/hour-calm/` as its own idea.
