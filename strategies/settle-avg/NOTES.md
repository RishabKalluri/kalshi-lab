# Settlement-average lock-in taker (settle-avg)

Agent run 20261022-0128-2 (brief: KXSOL15M, own idea). Series ETH + XRP + SOL (BTC/DOGE left out only to keep the
full test short).

## Hypothesis (written before any engine test)
In the last 45 s the 60 s settlement average (CF index) is partly fixed. Binance 1 s + the open basis tracks it to
~1.7 bp (measured: `$RUN/s/basis.py`, std of basis change over a window). Model P(YES) = Phi((E[avg]-K)/sd) with the
known seconds, a random walk for the rest, and the basis noise. Kalshi quotes in the last minute are wide.
- **Who loses:** makers/takers pricing off the last spot print; buyers who hit the touch earn the model gap.
- **Screen (dev data, trade prints, `$RUN/s/lastmin.py`, first print per market with model P >= price+gap, price
  60-98c, last 45 s, net of fee):** ETH gap 2-5c +4.1c (se 0.9, 1,101 mkts, 9/9 months), >10c +11c; XRP +2.3c; DOGE +1.7c; SOL +3.2c
  (Jun/Jul ~0). Gap itself is calibrated (model P matches outcome rate in the selected set).
- **Contradicts** `settle-lockin` (rejected: log loss worse than next-fill mid; SOL flips). That test averaged over
  all fills; this one trades only the large-gap subset on printed asks.
- **Wrong if:** engine fills (150 ms, depth) remove it, full walk-forward not promising, months flip, lockbox
  (real recorded books Oct) loses.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-22 | v1: gap 3c, tau 4..45, 5 coins | smoke | ok, 4 mkts in 6 h | (worker error on results write: folder was not group-writable; fixed with chmod) |
| 2 | 10-22 | same | quick (4 days, 5 coins) | -3.2c/ct, 48 mkts, CI -16..+9 | noise-sized sample, passes the gate |
| 3 | 10-22 | same, series ETH+XRP+SOL (BTC/DOGE dropped for runtime) | full 1/3 (job settle-avg-1022-020809, 4 h wall) | **promising** +3.66c/ct, CI +1.91..+5.33, 1,869 mkts, 7/7 months positive (Feb +6.3, Mar +4.8, Apr +0.1, May +4.0, Jun +1.1, Jul +2.2, Aug +7.0), 2x latency +3.95c (CI +0.70..+7.11, Jun-Aug) | edge is not just the thin era: Jun-Aug still +1..+7c. Day-level 126/202 positive |
| 4 | 10-22 | same | lockbox (job settle-avg-1022-060357) | queued | real recorded books Oct; result below |
