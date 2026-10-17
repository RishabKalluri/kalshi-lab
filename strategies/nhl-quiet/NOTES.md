# NHL quiet-window maker (nhl-quiet)

Agent run 20261016-1947-1 (brief: trade against retail flow in quiet stretches, weather + sports). derived_from pregame-maker.

## Hypothesis (written before any pipeline run)
Taker edge (outcome of the side bought minus price paid, contract-weighted, clustered by game) on development data:
NHL pre-game -1.5c (CI -2.9..-0.1), NHL intermissions -1.57c (CI -2.6..-0.6, game-eq -1.59), NHL live play -0.29c; NBA
takers lose nothing anywhere (+0.5c pre, +0.06 live). Markouts of NHL pre-game takers are ~0 (mk5 +0.05c), so a maker
at the touch is not picked off by news there; the maker fee is 0.44c at 50c. So net ~1c/contract for a back-of-queue
maker that quotes pre-game and inside the two intermissions and is out during play.
Wrong if the walk-forward pooled CI (net of maker fee) <= 0 or the lockbox loses.

## Research (research/)
- screen.py: per-trade parquet (edge, markouts 1/5/30/60 min) for the series; sp_buckets.py / wx_buckets.py: buckets.
- nhl_windows.py: ESPN intermission windows vs the start estimate (expected_expiration - 171 min): ESPN start - est
  median -0.1 min (IQR -0.5..3.2); intermission 1 starts 37.7 min after the estimate (IQR 35.1-41.2), intermission 2
  at 94.8 (91.0-99.3), each lasts 18.5 min -> fixed windows i1 [42, 53], i2 [100, 109] sit inside the break in most games.
- fills_win.py: per-ESPN-phase PnL of a run's fills.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-16 | v1 smoke on one ad hoc week (Mar 2-9) | ad hoc | -4.1c, 108 mkts | mechanics ok |
| 2 | 10-16 | v1 ad hoc Jan 7 - Apr 30 (books, --timeline-s 0, qty 20, engine maker fee) | ad hoc, 4 months | **pooled net -2.06c/contract, CI -3.52..-0.63, 611 games, 151.6k contracts**; Jan -1.4, Feb -1.0, Mar -4.2, Apr 0.0; by ESPN phase: pre +0.5c (481 games), intermission 1 -3.5c, intermission 2 -4.9c (CI -9.1..-1.1), live -0.75c | no pipeline run: CI < 0 |

## Learnings
- Taker edge (outcome minus price paid) by time bucket does not tell what a resting quote earns: the quote is filled when the book is about to move (restart of play, news, a large taker), which is the adverse-selection part the taker average does not contain.
- Intermission quotes are the worst: fills there lose 3.5-4.9c net although takers in intermissions lost 1.6c on average.
- NBA takers lose nothing in any phase; NHL pre-game takers -1.5c; weather takers -0.7c at every local hour.
- ESPN-derived NHL timing (research/nhl_windows.py): intermissions last 18.5 min, start 37.7 (IQR 35-41) and 94.8 (91-99) min after expected_expiration - 171 min.
