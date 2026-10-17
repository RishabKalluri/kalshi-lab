# Infrastructure needed to run sports maker strategies through the pipeline (not applied: protected files)

## 1. Engine timeline memory (blocks every stage on sports books)
`Engine._sample` appends a dict per ACTIVE market every `timeline_s` (default 5 s; the pipeline passes no flag). Sports game markets are
discovered ~2.5 days before the game, so ~60-100 are active at once: ~13 GB per month for NBA+NHL (1 week = 3.5 GB; NBA alone ~6.5 GB/month),
and the pipeline runs 3 months at a time inside a 6 GB sandbox (`kalshi-sandbox`: MemoryMax=6G). Job `sports-tails-1016-010959` (full) died within
~2 minutes, before any month finished, with an empty log tail. Ad-hoc runs with `--timeline-s 0` use 0.3-1.5 GB and finish a month in 6-10 minutes.
Smallest fix (chart output only, no effect on results): in `Engine.__init__`

    self.timeline_ns = int(timeline_s * NS) if timeline_s and getattr(strategy, "sample_timeline", True) else None

then set `sample_timeline = False` on the strategy class (not added to the strategy here: without the engine change it would do nothing),
or make `validate.run_backtest` pass `--timeline-s 0` when `source == "books"`.

## 2. Maker fees in backtests
`backtest.run_one` builds `SimExchange(fees=Fees())`: maker rate 0 for every series, although most sports game series charge makers
0.0175*p*(1-p) (fee_type quadratic_with_maker_fees; https://next.io/prediction-markets/kalshi/fees/). Pipeline cards for maker strategies on
KXNBAGAME/KXNHLGAME are therefore overstated by the maker fee (0.14c for sports-tails, 0.44c at mid prices). Fix: `Fees(maker_rate=0.0175)` for
series whose fee_type is quadratic_with_maker_fees (`Fees.for_series` already exists but the backtest does not use it). Until then use
strategies/pregame-maker/research/fills_pool.py to recompute net-of-fee numbers from fills.csv.

## 3. Smoke / quick windows
The smoke (last 6 h before the lockbox) and quick (last 3 days) windows end Aug 31: no NBA/NHL games, so both stages trade nothing for sports.
