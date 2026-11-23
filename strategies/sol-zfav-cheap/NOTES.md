# SOL cheap spot-confirmed favourite, maker (derived_from sol-zfav-early)

Markets: KXSOL15M. Agent run 20261108-0057-2.

## Hypothesis (written before any pipeline test)
- sol-zfav-early's rule (post-only bid one tick inside the spread on the side SOL spot is >=1.5 sigma past the strike, 540..300 s
  to close) restricted to fills where the favourite costs <= 90c (`max_px=900`).
- Why: in the engine's walk-forward fills (dev months, fills.csv x markets.csv, `research/band.py`) the edge per contract falls with
  the favourite's price in every coin's zfav maker run: SOL early 8.1c (n=436) at <=90c vs 0.9c at 95-97c; SOL parent 6.8c vs 0.6c;
  XRP 4.6c vs 0.9c; DOGE 5.3c vs 1.5c; ETH+BTC 1.4c vs 0.7c. When the quote sits far below the spot-implied probability the
  market hasn't absorbed the confirmation yet and the nervous seller who hits the bid is the counterparty; near 97c the
  fee-free spread is competed away.
- Wrong if: full walk-forward < +3c/contract or CI includes 0, edge in 1-2 months only, 2x latency loses, lockbox not profitable.
- Disclosure: the 90c cut was chosen after looking at dev fills by price band (4 coins). Cross-coin replication is the guard;
  the lockbox is the clean test. Opportunity: ~50 fills/month on SOL (436 in 9 months of the parent's windows), so a thin sample.

## Screens behind it (this run; scripts for the others were lost with a deleted scratch folder, results below)
- Virtual maker fills from the tape (bid+1c fills if a taker sold at <= our price within 30 s), Jan-Sep dev: EV per fill is a
  monotone function of signed z only (z>=1.5: +1.7c; z in -0.5..0.5: -1.5..-2.7c = adverse selection). A walk-forward GBM on
  z, h, price, vol ratios, trade count, spread, hour, dow did not beat the z>=1.5 rule (pred/pay corr 0.013; top-15% +1.6c vs +1.7c).
- Price band in the virtual sim agrees: z>=1.5 fills at 0.90-0.94 +4.1c, at 0.96-0.98 +0.9c.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 11-08 | v1 max_px=900 | smoke | fails only because the 6 h smoke window has no cheap-band fill | ad hoc Sep 1-8: 49 mkts, +11.9c/ct |
| 2 | 11-08 | v1 | quick | passed, 25 mkts, +1.8c (CI -13.5..+12.3, noise; 3 days) | thin sample, as expected |
| 3 | 11-08 | v1 | full 1/3 (job sol-zfav-cheap-1108-011620) | **promising**: +6.43c/ct, CI +3.43..+9.88, 627 mkts, 5,635 contracts, 145/175 days; months Jan +24.0, Feb +4.5, Mar +8.6, Apr +16.0, May -4.8, Jun +6.4, Jul +10.9, Aug +1.6, Sep +4.0 (8/9); 2x latency pooled (Jul-Sep) +4.97c, CI +1.59..+8.13 | edge per contract is large but thin (~70 mkts/month) and weaker in Aug-Sep (liquidity growth); the 90c cut is dev-informed (disclosed) |

## Learnings
- Same rule as sol-zfav-early but only 627 of its 4,784 markets; those carry ~16% of its contracts and (6.4c vs 2.3c) most of its PnL per contract.
- Capital-wise cheap-band fills are rare: ~$360 over 9 months at the default sizing (0.5% of equity per order). Edge-proportional (Kelly) sizing across the
  whole zfav family would use this fact; sizing isn't part of the pipeline.

## Current status
- Stage: full promising; lockbox job sol-zfav-cheap-1108-041259 queued (one run, code unchanged).
