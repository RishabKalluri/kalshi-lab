# Rain NO on dry forecasts (rain-fc)

Markets: KXRAIN (22 cities). Agent run 20261020-0057-1. derived_from rain-no (same rule, one added filter).

## Hypothesis (written before the pipeline)
- Retail keeps YES around 25-30% on "will it rain" even when the day-ahead forecast has no rain left; dev: at 6 h left, dry-forecast markets (80%) priced 25.2%, resolved YES 11.6% (n=198); wet-forecast markets priced about right (15 markets >2 mm: price .45, yes .60).
- Counterparty: retail anchoring on a chance-of-rain floor. Wrong if full CI <= 0, 2x latency loses, lockbox loses, or the filter adds nothing over rain-no.
- Forecast: Open-Meteo previous-runs `precipitation_previous_day1` (run issued the day before, no lookahead) in `data/fc_<CITY>.csv`, fetched by `research/fetch_fc.sh` (forecast only, no outcomes; covers Jul 10 - Oct 20). Paper/live needs the same API called live (the strategy reads the csv; a live loader is needed).

## Dead side-hypothesis (research/, H1): station observations
IEM hourly METAR precip (p01i >= 0.01 in) predicts the resolution (175/178 YES) but the market already prices it: buying YES >= 5 min after the first measurable-rain report loses 12-39c (n 16-30); excluding already-rained days removes 6 of 224 rain-no entries; sky cover/dewpoint spread at entry add nothing.

## Iteration log
| # | change | stage | result |
|---|--------|-------|--------|
| 1 | v1: rain-no rule (6 h, YES bid 10-90c, taker-sell trigger) + remaining forecast <= 0.1 mm | quick (3 days) | passed (noise, 15 mkts); first attempt failed on folder permissions (chmod g+w needed for agent-created folders) |
| 2 | v1 | **full 1/3** | **promising** +15.83c/ct (CI +9.1..+22.4), 153 mkts, 2,499 ct, 35/42 days; Jul +26.0, Aug +11.0; 2x latency identical (synthetic book). rain-no unfiltered: +14.13c (163 mkts): the filter adds ~1.7c, within noise |

## Learnings
- The rain edge is a flat retail overpricing of YES when no rain is forecast; forecast information filters the few wet cases but doesn't change the picture.

## Status
developing; lockbox queued (job rain-fc-1020-010451).
