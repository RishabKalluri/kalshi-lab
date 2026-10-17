# Rain NO (rain-no)

Markets: KXRAIN ("Will it rain in <city> on <date>?", resolves YES if the NWS CLI precipitation total for the local day is
strictly greater than 0 inches; ~22 cities, one market per city-day, listed ~36 h before the close, close at local midnight).
History in backfill: 2026-07-16 -> 2026-10-12 (84 days; development = Jul 16 - Aug 31 = 42 days, ~830 city-days; lockbox = 42 days Sep-Oct). Trades only (no dev books; recorded books start Oct 13).
Agent run 20261016-1947-1 (brief: retail flow in quiet stretches). Found while screening taker PnL by series.

## Hypothesis (written before the pipeline runs)
- Why mispriced: the rule is strict (>0.00 in at the station); trace amounts and rain that misses the airport gauge resolve NO. Retail
  prices the forecast "chance of rain" (an areal number) and keeps buying the YES lottery ticket through the evening.
- Who is on the other side: retail YES buyers. Screen on development trades (research/ in nhl-quiet/research/rain.py): YES takers paying
  10-90c lose 7-17c/contract (contract-weighted, CI clustered by day), NO takers earn +6..+20c; the pattern holds in every hours-to-close
  bucket from 0 to 30 h, 35 of 42 days positive.
- Wrong if: the walk-forward pooled CI (net of taker fees) <= 0, the 2x-latency run loses, or the Sep 1 - Oct 12 lockbox (autumn frontal rain, tropical systems) loses.

## Caveats found while building
- The screen's "calibration by VWAP" table (markets priced 10-60% realised 1-20%) is contaminated: a contract-weighted average price
  over the last 6-24 h is dominated by late trades that already know the outcome. The tradable evidence is the engine run on fixed rules.
- Backfill has no books: the engine synthesizes bid/ask from the last taker-sell/buy trade (depth = book_depth 25). A bid from an old
  trade is stale in a falling market, so v2 triggers only on a taker-SELL trade (that trade proves the bid), v1 triggered on any trade (optimistic).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-16 | v1: any trade, YES bid 5-60c, 2.5-24 h before close | smoke | no fills (window Aug 31 18:00-Sep 1 00:00 has no qualifying trade) | use --skip-smoke for weather |
| 2 | 10-16 | v1 | quick (Aug 29-31) | passed, +4.1c, 27 mkts, CI -13.6..+21.7 | noise |
| 3 | 10-16 | v1 | full (Jul 16 - Aug 31) | **inconclusive** +3.44c/contract, CI -0.93..+7.59, 456 markets, Jul +7.4c, Aug +2.1c (2/2 months positive, 23/42 days) | full test 1/3 used |
| - | 10-16 | ad hoc dev runs before v2 (7 variants, logged): taker-sell-only trigger on v1 rule +6.1c t=2.7 (399 mkts); late window [0.5,6]h bid 10-90c +13.5c t=3.9 (158 mkts, 33/42 days, Jul +24c Aug +9.4c); [0.5,3]h +18.4c t=4.0 (79 mkts); [3,6]h +11.3c; bid bands: 10-20c +9.6c, 20-40c -2.3c, 40-60c +26.8c, 60-90c +25.5c | | | v2 chosen from the ttc table of the taker screen (NO takers +10..+15c within 12 h of close), not from the lockbox. 124/158 entries happen in the first hour of the window (ttc 5-6 h) |
| 4 | 10-16 | v2 (defaults: last 6 h, bid 10-90c, taker-sell trigger) | quick (Aug 29-31) | passed, -10.2c, 17 mkts, CI -31.9..+10.9 | noise (3 days) |
| 5 | 10-16 | v2 | full (Jul 16 - Aug 31) | **promising** +14.13c/contract, CI +6.95..+20.92, 163 markets, 32/42 days, Jul +24.0c (CI 10.4..36.9), Aug +9.9c (CI 2.1..17.4); 2x latency identical (backfill book is synthetic) | full test 2/3 used |
| 6 | 10-16 | v2 unchanged | **lockbox (Sep 1 - Oct 12)** | **pass**: +4.51c/contract, CI -2.09..+12.31, 117 markets, 1,922 contracts, +$86.6 on the $1000 test bankroll, 27/39 days positive, max drawdown $33 | the edge shrank by ~2/3 out of sample (14.1c -> 4.5c); still profitable; the CI includes 0, so "pass", not "strong pass" |

- The lockbox stage also ran the strategy on the recorded REAL books (Oct 13-16, 4 days): **-11.5c/contract, 13 markets, 245 contracts, CI -31.7..+8.1** (not part of POOLED; Sep +4.0c on 94 markets, Oct 1-12 +6.3c on 23 markets). Tiny sample, but it is the only run with real quotes: paper trading must check whether the bid at ~18:00 local is really where the trade-synthesized bid is.

## Learnings
- Retail overpays for rain: the strict ">0.00 in at the station" rule vs a forecast chance-of-rain mindset. Dev edge +14c, lockbox +4.5c.
- Screens of takers by hours-to-close are tradable evidence only as fixed rules in the engine; VWAP-by-window calibration leaks the outcome.
- Backfill books are synthesized from the last trade: trigger on trades that prove the quote (taker-sell for a bid), and expect real fills to be worse (spread, depth 25 assumed). Paper on the recorded KXRAIN books (Oct 13 on) is the check.
- Real-book lockbox days (4 days, 13 markets) lost -11.5c: the synthetic bid may be optimistic; this is the first thing paper must resolve.
- Entries are bunched at the window open (124 of 158 within the first hour, ~18:00 local); sizing is limited by the book depth at that moment.

## Current status
- **paper_candidate** (lockbox passed 2026-10-16). Family: only this folder (nhl-quiet and other screens in this run did not feed it). Lockbox run used (1/1 this period). Full tests used 2/3.
- Before live: `kalshi-lab audit rain-no`, results.json must match the ledger; weather has no maker fee, taker fee 0.07*p*(1-p).
- Risks: (1) one season only (Jul-Oct); winter/snow-season drizzle frequency differs; (2) 42+42 days and weather days are cross-city correlated (frontal days), so the effective sample is ~84 clusters; (3) tail: a NO bought at 90c loses 90c on 19% of entries; (4) the lockbox edge was 1/3 of the dev edge.
