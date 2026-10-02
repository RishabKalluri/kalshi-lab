# US-Hours Vol Seasonality

Markets: KXETH15M (primary), KXSOL15M (second). KXBTC15M as a control (efficient market).

User's hypothesis: a coin's volatility profile is fundamentally different depending on whether US markets are open;
maybe extend to other markets or to hours of the day generally.

Why ETH/SOL: the thinner 15-minute markets are the ones with measurable vol-pricing errors (eth-volfav, sol-vomma);
BTC prices vol correctly and serves as the control.

## Hypothesis 1 (written before any test): the market prices vol off the recent past and misses scheduled vol changes
- **The vol fact (to check first):** crypto intraday vol has a strong, *scheduled* shape tied to US trading: a jump
  at 8:30 ET (US macro releases), at the 9:30 ET equity open and 10:00 ET (more releases), elevated through the US
  session, a drop after the 16:00 ET close, and much lower on weekends. If it's really about US markets, the vol
  peak should sit at a fixed *New York* time and move by one hour in UTC when US clocks change (Mar 8, 2026).
  The 15-minute windows line up exactly with 8:30, 9:30, 10:00 and 16:00 ET.
- **Why the market should be mispriced:** a Kalshi trader (or quoting bot) looking at the last few minutes of
  price action prices the remaining move at *recent* vol. Just before a scheduled vol step up (the 9:30 window,
  8:30 release window) recent vol understates what's coming, so implied vol is too low and the underdog is too
  cheap; just after a step down (the hour after 16:00 ET, Friday evening into the weekend) recent vol overstates
  it, implied vol is too high and the favourite is too cheap. Away from transitions, recent vol ≈ upcoming vol
  and there's nothing to take.
- **Who is on the other side:** retail takers and simple quoting bots that use trailing realized vol (or eyeball
  the chart) without a time-of-day prior.
- **What would prove this wrong:** (1) the vol seasonality isn't there or isn't tied to US hours (no DST shift);
  (2) the gap log(iv) − log(rv_fut) doesn't vary by ET time bucket beyond noise, or doesn't follow the
  "transition" pattern (too low before step-ups, too high after step-downs); (3) at real next fills, after the
  taker fee, buying the underdog where iv is too low / the favourite where iv is too high isn't positive in both
  halves of development data (Jan–Apr, May–Aug 19). Also: if it only works where eth-volfav already trades
  (iv high, favourite side), it's the same edge.

## Hypothesis 2 (written before screen 5): weekend vol is mispriced
- Weekend vol is 0.6–0.9× weekday. If Kalshi traders carry weekday vol into Saturday/Sunday (or weekend vol into the
  Monday Asia session), iv/rv_fut is too high on weekends and the favourite is cheap. Wrong if weekend log(iv/rv_fut)
  is no higher than on weekdays, or favourite PnL at next fills isn't positive in both halves.

## Strategy v1 (after screens 1–4): OpenUnderdog
- On NYSE trading days, in the window starting 9:30 ET, at checkpoints h = 600/480/360/300/240 s, buy the underdog
  (10–45¢) at the touch, once per market, hold to settlement. Series: **ETH and BTC together** (both positive in both
  halves at 9:30; SOL wasn't, so it's left out: a choice made after looking, noted here). One trade per coin per
  US trading day, so ~2 markets/day; the sample will be small (~300 markets in the walk-forward).

## Hypothesis 3 (written before screen 6): the 8:30 ET macro-release step is underpriced like the bell
- 8:30 ET is when US data comes out (jobless claims every Thursday; CPI, NFP, PPI, retail sales on other days). Vol in
  that window is +0.4 above the weekday mean. If the market misses it as it misses 9:30, the underdog is cheap there too.
  Wrong if log(iv/rv_fut) at 8:30 is normal, or the underdog isn't positive in both halves.

## Hypothesis 4 (written before screen 7): the 16:00 ET close step-down is priced late
- After the US close, vol drops (16:15–16:45 below the daily mean). If the market carries session vol into the evening,
  iv is too high and the favourite is cheap. Wrong if favourite PnL at next fills isn't positive in both halves.

## Ideas and prior work used
- `strategies/eth-volfav/` (implied-vol math, HAR forecast with UTC-hour dummies, fixed checkpoints). Its notes say the
  edge is concentrated *outside* US afternoon hours.
- `strategies/btc-anchor-vol/research/bias_scan.py`: no weekend × hour price bias positive in both halves (a price-level
  scan, not a vol-level one).
- IDEAS.md "Time-of-day and weekend regimes" and "Scheduled macro events".

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-02 | `research/seasonality.py`: per-window realized vol (rv_fut at h=840, demeaned by month) by window start, UTC vs NY clock, before/after the Mar 8 DST change, weekday/weekend | research | **The user's hypothesis holds strongly.** EST vs EDT intraday profiles correlate 0.97 on the NY clock vs 0.74–0.80 on UTC (all three coins). Weekday log vol vs the month's mean: 9:15 ET window +0.28 (ETH), **9:30 window +1.03** (≈2.1× the 9:15 window), 10:00–11:00 +0.6..+0.8, 8:30 +0.40 (macro releases), after 16:00 ET −0.1..−0.2. Weekends 0.68× (ETH), 0.87× (SOL), 0.62× (BTC) weekday vol | Vol is set by US equity hours, not by UTC hours. The 9:30 ET open is the largest scheduled vol step of the day. eth-volfav's UTC-hour dummies smear it by an hour for half the year. |
| 2 | 10-02 | `research/iv_gap.py`: by NY 15-min slot (weekdays), median log(iv/rv_fut), log(iv/rv_15m), and underdog/favourite PnL at the next real fill after fee, halves A (<May) / B (May–Aug 19) | research | Only the **9:30 slot** stands out: early in the window log(iv/rv_fut) −0.12 ETH, −0.18 SOL, −0.09 BTC vs +0.17/−0.10/+0.24 on average (≈0.3 too little vol), while trailing rv understates by 0.36. Underdog PnL in the 9:30 slot, mid window (h 240–480): ETH +13.3/+6.7¢, SOL +0.9/+11.3¢, BTC +4.2/+6.9¢ vs a −2..−3¢ baseline. 16:00 slot (vol step down) has iv too high but the favourite isn't reliably positive | The market partly adjusts (iv/trailing is higher than usual at 9:30) but not enough. |
| 3 | 10-02 | `research/open_dog.py`: 9:30 window, underdog 10–45¢, first checkpoint h 240–600 per market, by horizon, month, price; placebos (weekends and NYSE holidays at 9:30) and neighbouring slots | research | **ETH +10.9¢ (se 4.2), 119 markets, 7/8 months positive** (Aug −12.4, n=11); **BTC +7.0¢ (se 3.9), 140 markets**; SOL −0.5¢ (se 4.3). Placebos: weekends 9:30 −4.7¢ ETH / +0.4 BTC, holidays −4.9 / −3.4 (small n). 9:15 and 9:45 slots ≈ baseline or worse; 10:00 mixed | Effect is tied to the bell itself (gone on weekends/holidays, absent in neighbouring slots). Not a thin-market effect: BTC has it too, SOL doesn't. |
| 4 | 10-02 | `research/slot_model.py`: generalise: HAR (+rv_5m) forecast with NY-slot dummies (weekday/weekend × early/late in window) vs UTC hours, fit A, test B; deciles of log iv − forecast | research | NY slots barely raise out-of-sample R² (ETH 0.625→0.630, BTC 0.485→0.492): rv_5m catches the burst once it starts. Bottom decile (iv low vs forecast) underdog −2.3/+1.0 (ETH), −2.6/−1.8 (SOL), −0.4/−1.1 (BTC); not tradeable | A general "vol below seasonal forecast" signal is dead (as btc-anchor-vol found with HAR). Only the specific 9:30 slot is worth a pipeline test. |
| 5 | 10-02 | `research/weekend.py` (**H2**: weekend vol is 0.6–0.9× weekday; is it priced?) | research | Weekend log(iv/rv_fut) within ~0.05 of weekdays on all three coins; favourite PnL ≈ −0.4..+1.2¢ (both halves mixed), Mon 00–04 ET +2.8/+2.2¢ ETH but BTC +0.2/−2.7 | **H2 rejected at research:** the market prices the weekend vol level correctly. |
| 6 | 10-02 | `research/macro_830.py` (**H3**: is the 8:30 ET macro-release window's vol step underpriced like 9:30?) | research | 8:30 vol is +0.1..+0.4 above the weekday mean on every weekday, but log(iv/rv_fut) there is normal (ETH 0.04–0.30, BTC 0.13–0.32); underdog PnL flips sign between halves on every weekday (Thu ETH +6.4/−10.6) | **H3 rejected at research:** the market prices the 8:30 release step. Only the 9:30 bell surprises it. |
| 7 | 10-02 | v1 OpenUnderdog, ETH+BTC, ad-hoc Jun 2026 | ad-hoc | +13.5¢/ct, 33 markets, t 1.4 | mechanics as intended, matches research for June |
| 8 | 10-02 | v1, smoke with slots widened to 13:00–20:45 ET (the smoke window, 18–24 UTC Aug 19, has no 9:30 ET window) | smoke | passed (44 markets) | mechanics only |
| 9 | 10-02 | v1 (job us-hours-vol-1001-220450) | quick | passed: 3 markets, −39.9¢ | noise (3 markets) |
| 10 | 10-02 | v1 (job us-hours-vol-1001-220621) | **full (1/3): inconclusive** | **+3.16¢/ct, CI −2.54..+9.09**, 10.1k contracts, 258 markets, 5/9 months positive (Dec −22.4 n13, Jan −2.5, Feb +17.6, Mar +6.4, Apr −7.8, May +6.9, Jun +13.5, Jul +5.4, Aug −10.5); 2× latency Jun–Aug +4.46¢; ETH +3.5¢, BTC +2.9¢ | About a third of the research's +9¢. Diagnosis: 28 of 258 fills paid > 3¢ above the mid (wide/stale backfill quotes in the opening burst) and lost −13.8¢/ct; the other 225 made +4.8¢. Change one thing: skip checkpoints with spread > 6¢ (`max_spread=60`). Post-hoc, motivated by not paying through wide quotes. |
| 11 | 10-02 | `research/close_fav.py` (**H4**: mirror of the bell: after the 16:00 ET close vol steps down, so the favourite should be cheap in 16:00–17:00 windows) | research | Favourite PnL by slot flips sign between halves and coins (ETH 16:45 +0.6/+12.7, 16:15 −5.2/−6.1; BTC 16:00 −8.7/−12.8); no slot positive in both halves on two coins | **H4 rejected at research.** The market isn't slow to price the vol step *down*; only the step up at the open surprises it. |
| 12 | 10-02 | v2 = v1 + `max_spread=60`: smoke (widened slots) passed; quick (job us-hours-vol-1001-224031) passed, 3 markets | smoke/quick | passed | |
| 13 | 10-02 | v2 (job us-hours-vol-1001-224148) | **full (2/3): inconclusive** | **+4.32¢/ct, CI −1.49..+10.46**, 9.7k contracts, 237 markets, **6/9 months positive** (Dec −14.1 n6, Jan +1.9, Feb +14.8, Mar +8.3, Apr −8.4, May +8.4, Jun +13.5, Jul +5.4, Aug −10.1); 2× latency Jun–Aug +4.78¢ (CI −5.3..+15.5); max drawdown $176 | The spread filter did what it should (+3.2 → +4.3¢, 5/9 → 6/9 months). Everything points the right way except the pooled CI, and that is a sample-size problem: one market per coin per US trading day gives ~240 markets in 8 months, so even a real +4¢ edge has a CI of about ±6¢. Another parameter change won't fix that, so the third full test is held back. |

## Learnings
- **Crypto vol runs on the New York clock.** Across the March DST change the intraday vol profile matches on NY time
  (corr 0.97) and not on UTC (0.74–0.80), for BTC, ETH and SOL. The 9:30 ET window is the most volatile 15 minutes
  of the weekday (~2× the 9:15 window); 8:30 (macro data) and 10:00–11:00 are elevated; after 16:00 is quiet; weekends
  are 0.6–0.9× weekdays. Vol models with UTC-hour dummies (eth-volfav's) are off by an hour for ~8 months a year.
- **Kalshi prices almost all of this correctly:** weekend vol, the 8:30 release step, the 16:00 step down, and the
  general level once the burst has started (rv_5m catches it, so NY-slot dummies add ~0.005 R²).
- **The one gap is the opening bell itself:** in the 9:30 window implied vol is ~0.3 log points too low relative to
  realized vol, on ETH and BTC (and SOL by the iv measure), and the underdog is underpriced. It vanishes on weekends
  and NYSE holidays at the same clock time, and isn't in the 9:15 or 9:45 windows. The engine finds +4.3¢/contract
  (6/9 months), about half the research figure.
- **Wide quotes in the opening burst are a trap:** fills more than 3¢ above the mid lost −13.8¢/contract.
- **A one-window-a-day strategy can't reach significance on 8 months of two coins.** ~240 markets gives a CI of about
  ±6¢. More markets, not better parameters, would settle it.

## Current status
- Stage: **parked, inconclusive after full test 2 of 3** (+4.32¢/ct, CI −1.49..+10.46, 6/9 months, positive at 2× latency).
  The lockbox wasn't run, because only a promising full may use it.
- Not tried on purpose: a 3rd full with another tweak. The issue is sample size, not the rule.
- What would settle it: more independent markets with the same bell. (1) Other coins' Kalshi 15-minute markets
  (XRP, DOGE, ... if Kalshi lists them), or (2) history before Dec 2025, if the series existed. Either needs a download
  by the user. With the same rule on 3–4 coins, the last full test could reach a CI above 0 if the edge is real.
  SOL is in the data and could be added for a no-tweak rerun, but its research result was −0.5¢, so on its own it
  would most likely dilute the edge.
