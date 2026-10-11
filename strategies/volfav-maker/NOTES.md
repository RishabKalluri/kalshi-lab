# VolFav Maker

Markets: KXETH15M. `derived_from: eth-volfav` (same signal, same vol model and threshold; only execution differs).
Came out of `strategies/vol-burst/` H6 (that folder holds the five rejected vol screens that preceded it).

## Hypothesis (written before testing)
- **Why mispriced:** eth-volfav's taker edge (~+2c/contract) is about what fee + spread cost on ETH (~3-5c), so
  the same signal executed passively should keep several cents more per contract, *if* our fills aren't adversely
  selected.
- **Who's on the other side:** the same reversal-buying underdog takers eth-volfav trades against, now selling the
  favourite into our bid instead of us lifting their offers.
- **Proved wrong if:** per-contract result isn't above eth-volfav's taker result on the same signal, i.e. fills
  on the signal are adversely selected like dog-seller's back-of-queue fills (-2.1c within 30 s).

## How it works
At eth-volfav's checkpoints (T-360..T-60 s), when iv / HAR forecast > the fitted 70th percentile: post a post-only
bid for the favourite one tick above its best bid (join it when the spread is one tick), cancel after 25 s or at
T-45 s. `take=1` switches to eth-volfav's IOC-at-the-ask execution for a like-for-like comparison.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-10 | research (vol-burst/research/maker_fav2.py): signal rows, penny-jump fill proxy = any taker sell within 10 s | research | +2.9 / +2.3 / +4.2c per filled ct (Dec-Apr / May-Jun / Jul-Aug) vs taker +0.8 / +0.6 / +2.9c | looked like +1.5-2c from execution |
| 2 | 10-10 | engine ad hoc, May 1-15, model fit until May 1 | backtest | **-0.14c/ct**, 3,350 ct, 201 markets, 60% of quotes filled. Decompose: edge at fill +2.8c, **adverse next 30 s -5.7c**, carry +2.7c | the engine fills us on every taker sell that trades through our price within 25 s, including fast drops; the screen only looked at the first trade |
| 3 | 10-10 | engine ad hoc, Jun 1-Jul 31, model fit until Jun 1, maker vs taker on the identical signal (`--sweep take=0,1`) | backtest | maker **+0.77c/ct** (7,800 ct, 519 markets, t 0.39) vs taker **+1.77c/ct** (11,032 ct, 671 markets, t 1.12; fees $128) | **Maker is worse than taker on the same signal**: what it saves in fee + spread it loses to adverse selection, and it misses ~30% of the signal's markets |

Stopped before the pipeline: the hypothesis's own falsification test (maker per-contract above the taker's on the
same signal) failed in 2.5 months of engine runs, by ~1c/ct in the same direction in both periods. A full test would
spend a budget to confirm it. Budgets untouched (0/3 full, lockbox unused).

## Learnings
- **Volfav's signal can't be made passively on backfill without giving the edge back.** Takers who sell the favourite
  into a penny-jumped bid a few minutes before close are informed often enough (-5.7c in 30 s) to cancel the
  ~3c saved on fee + spread. Same lesson as dog-seller, now with a positive-edge signal behind the quote.
- **Fill-proxy screens flatter makers**: "first taker trade within 10 s" misses the fills you get as the price runs
  through you. Use the engine for anything maker.
- Caveat: backfill books are synthetic (last trade prices, fixed depth). Real queue behaviour only exists in the
  recorded books, which are all lockbox-era. If the user ever wants a real-book check, run `take=0` in a spare paper
  slot next to eth-volfav's paper trader; that would test execution, not prove an edge.

## Current status
- Stage: **rejected** (engine ad hoc, before smoke/quick/full).
