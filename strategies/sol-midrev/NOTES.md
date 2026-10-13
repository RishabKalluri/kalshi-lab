# SOL Late-Confirmed Reversal (folder sol-midrev)

Markets: KXSOL15M (Kalshi 15-minute SOL up/down; YES if the 60 s average of the CF SOL index before close is at
least the 60 s average before open).

Why SOL: it's the strongest open lead in `IDEAS.md`. eth-overreact's reversal is about twice as large on SOL in research
(+5.6¢, t 4.0), and eth-midrev's late-confirmed split holds on SOL too (research +7.7/+9.7¢ in Jan–Apr / May–Aug,
vs +8.0/+1.2¢ for the unconfirmed rest). Neither has been run through the engine on SOL. SOL's market is thinner than
ETH's, which is where the measured inefficiencies live (BTC efficient, ETH not).

## Hypothesis (written before any test)
- **Why the market should be mispriced:** consecutive 15-minute crypto returns reverse after big moves, most strongly
  when the move runs *into* the :00/:15/:30/:45 boundary (eth-midrev `research/offset_rev.py`, `boundary_shape.py`:
  SOL, ETH and BTC alike). Candle-close traders and hedgers of 15-minute binaries rebalancing into expiry push the
  last minutes; that overshoot gives some back after the open. KXSOL15M's opening price treats the new window as a coin
  flip and ignores it.
- **Who is on the other side:** opening takers and quoting bots pricing the window as driftless, and momentum buyers
  of the side the last window favoured.
- **The rule is fixed in advance:** eth-midrev's `LateConfirmed`, unchanged. |z15| > 1.5 (previous window, strike to
  strike, rv_60m units), |z5| > 1.5 for the last 300 s before the open (60 s averages), same sign; buy the reversal
  side at the touch at the first of h = 870/840/810/780 s with mid in 30–70¢; hold to settlement. Every parameter was
  set on ETH, so SOL is an out-of-sample transfer; no SOL tuning.
- **What would prove it wrong:** the full walk-forward isn't promising (pooled CI ≤ 0, < 60% of months positive, or
  loses at 2× latency); May–Aug is flat or negative (eth-overreact's decay); or the lockbox loses.
- **Known risks:** SOL books are thinner (fills at the touch may be worse than backfill trades suggest); trades overlap
  with any SOL version of eth-overreact (none exists).

## Ideas and prior work used
- `strategies/eth-midrev/` (rule, strategy.py, research/late_move.py SOL numbers), `strategies/eth-overreact/`
  (`reversal_stats.py`: SOL P(opposite | big move) 57.4%, fade +5.6¢), `strategies/sol-vomma/` (SOL vol model failed
  the lockbox: a reminder that SOL walk-forwards can flatter).

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-07 | v1: eth-midrev `LateConfirmed` copied unchanged | smoke | failed: no fills (6 h window Aug 19 18:00–24:00 after a 1 h warm-up had no trigger; SOL fires ~1.6/day) | Not a code fault. Mechanics checked ad hoc instead. |
| 2 | 10-07 | v1 ad-hoc Jun 1–15 | ad-hoc | 23 orders, all filled, both sides, +$7.44 on 328 contracts | Trades as intended. |
| 3 | 10-07 | v1 (job sol-midrev-1006-215759) | quick | passed: +7.81¢/ct, 52 contracts, 4 markets, t 0.28 | Noise-level sample; go to full. |
| 4 | 10-07 | v1 (job sol-midrev-1006-215837) | **full (1/3): promising** | **+8.77¢/ct, CI +3.65..+13.69**, 5.0k contracts, 354 markets, **7/8 months positive** (Jan +14.9 n18, Feb −2.4, Mar +12.8, Apr +17.8, May +13.0, Jun +0.7, Jul +10.7, Aug +11.0); 2× latency Jun–Aug +4.22¢ (CI −4.2..+12.9); max drawdown $67 | Larger than ETH (+5.4¢), as the research said; May–Aug ≈ +8¢, no decay. Go to the lockbox, code unchanged. |
| 5 | 10-07 | v1 (job sol-midrev-1006-221058) | **lockbox: pass** | **+2.11¢/ct, CI −7.33..+10.81**, 1.6k contracts, 112 markets, 23/44 days; Aug 20–31 +4.8¢ (31 mkts), **Sep −1.0¢** (73), Oct 1–7 +21.3¢ (8), recorded books −0.9¢ (5) | Pass, not strong pass. Far below the walk-forward's +8.8¢; Sep is flat. Either the edge is smaller than development data said or Sep was a bad month; paper can't tell which in weeks. |
| 6 | 10-07 | live-vs-Binance rv check (after the lockbox was spent): recorded composite (Coinbase/Kraken/Bitstamp median, as `ctx.spot`) vs Binance 1 s, Oct 1–7, 1 s diffs per hour | calibration | SOL Binance/live rv ratio median **1.11** (93 h); ETH measured the same way **1.01** | Paper uses rv_scale=1.11 so live z matches the backtest's Binance z. |
| 7 | 10-07 | `paper-start` (rv_scale=1.11, slip_c=1, 0.5%/order) | paper | started on the server as kalshi-paper@sol-midrev (4th of 4 slots) | |

## Learnings
- **The late-confirmed reversal transfers from ETH to SOL with no retuning.** ETH-set parameters gave +8.8¢/ct in SOL's
  walk-forward (CI +3.6..+13.7, 7/8 months, May–Aug no decay), larger than ETH's +5.4¢, as the thinner-market story says.
- **But the lockbox was much weaker** (+2.1¢, CI −7.3..+10.8; Sep −1.0¢ on 73 markets). Same pattern as sol-vomma
  (strong SOL walk-forward, weak lockbox), though this one stayed profitable. Treat SOL walk-forward sizes with suspicion.
- Smoke can fail for rare-trigger rules (SOL fires ~1.6/day; the 6 h smoke window had none). An ad-hoc dev-date
  backtest is the honest mechanics check; don't loosen thresholds to make smoke trade.
- Live composite vs Binance rv: SOL 1.11, ETH 1.01 (Oct 1–7). ETH paper traders use rv_scale=1.09; worth re-checking.

## Current status
- Stage: **parked** Oct 13: paper paused to free a slot for xrp-volfav (strong lockbox pass). Paper Oct 7-13: -$22.84 on 16 fills (0.5%/order, slip_c=1, rv_scale=1.11) on a weak lockbox pass. Full 1/3 used (promising); lockbox spent (pass).
- Next (if resumed): ~2 weeks of paper to check fills at the open on SOL's thinner books; then `kalshi-lab audit sol-midrev` and
  the user's OK. Given the weak lockbox, a live trial (if any) should be small.
