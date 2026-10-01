# Settlement Lock-in

Markets: KXETH15M (primary), KXSOL15M (same test, second market). YES if the simple average of the 60
seconds of the CF index before close is at least the 60-second average before open (the strike).

## Hypothesis 1 (written before any test): the settlement average is partly locked in
- **Why the market should be mispriced:** inside the last minute the settlement value is a 60-second
  average, and at τ seconds before close (τ < 60) a fraction (60−τ)/60 of it is already fixed. The remaining
  uncertainty of the average is only σ·√(τ³/3)/60, far smaller than a spot-vs-strike view (σ·√τ) suggests,
  and its centre is the *accumulated* average, not current spot. When spot has just crossed the strike but
  the average so far sits on the other side, a trader looking at spot vs strike thinks it's a coin flip
  while the outcome is close to decided (and vice versa). Before the window opens (60–180 s), the averaging
  also shrinks effective vol (the eth-volfav code uses τ − 40 as an approximation).
- **Who is on the other side:** retail takers reacting to the latest spot print (chasing a strike cross in
  the final seconds) and makers whose quotes key off spot distance.
- **What would prove it wrong:** (1) a partial-average probability model (Binance 1s + basis, plus the
  measured Binance-vs-CF noise) is not better than the next real fill's price in log loss / calibration;
  (2) buying the side the model favours at the next real fill, after the taker fee, is ≤ 0 in both halves
  of development data; (3) walk-forward months mostly negative.
- **Risk I know about:** sol-vomma found the market beats our spot-based models before the window (Binance
  vs CF basis error). Inside the window the accumulated average is a big, *known* part of the outcome, so
  the basis error matters less relative to the information advantage, if traders ignore it.

## Ideas and prior work used
- `strategies/IDEAS.md` "Last-minute momentum in ETH" (59% of 2σ settlement-minute moves continued): if
  real, it could be this averaging effect rather than momentum.
- `research/build_dataset.py` (spot arrays, basis = strike − our pre-open 60 s average); the settled
  market record's `expiration_value` (the CF close average) lets me measure Binance-vs-CF error directly.
- sol-flow/sol-vomma lesson: screen against next real fills, never the last-trade mid.

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-01 | `research/lockin_data.py` + `lockin_screen.py`: per market, 23 horizons from T−300 to T−3 s; partial-average model (Binance 1 s + basis, settlement average so far, remaining-path variance σ²τ³/3, plus Binance-vs-CF error measured from `expiration_value`), ETH and SOL, Jan–Aug 19 | research | Binance + basis tracks the CF average to ~0.2 of a 1-minute move (98.5% sign agreement with the outcome; a few markets have broken strikes). **Model log loss loses to the next-fill mid at every horizon** (h=30: 0.25 vs 0.16 ETH, 0.28 vs 0.17 SOL). Trading model−fill gaps: −1..−2¢ almost everywhere; 35–59 s bucket +2..+6¢ on ETH in both halves but SOL flips (+4.6 → −1.8¢) | The market knows the accumulated CF average better than we can reconstruct it (traders watch the CF RTI itself). |
| 2 | 10-01 | `cross_check.py`: rows inside the window where spot has crossed the strike against the projected average (the case a spot-watcher misreads) | research | ~1% of rows. Projected-average side wins 55–83%, priced at 51–78¢; PnL at fills −6..−11¢ in Jan–Apr, +1..+12¢ in May–Aug (n of 20–900) | No systematic misreading of the average: sign flips between halves. **Hypothesis 1 rejected.** |
| 3 | 10-01 | `late_fav.py`: generic late favourite-longshot bias (buy the favourite at fixed checkpoints T−300..T−3 s at the next real fill, by price bucket and month) | research | no bucket reliably positive; 80–97¢ favourites at 15–45 s: ETH −0.7¢, SOL −0.0¢ (clustered t ≈ 0); Jan–Apr mostly negative, May–Aug mostly positive on both coins | No late favourite-longshot bias; prices in the final minute are fair after fees. |

## Hypothesis 2 (side screen, same data): big Kalshi taker prints carry information (copy) or overreact (fade)
Written before the screen: if large takers (top 1% notional) are informed, the next fill on their side is still
cheap; if they're fat fingers or tilt, fading them pays. Wrong if both copy and fade lose about fee + spread.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 4 | 10-01 | `trades_dump.py` + `big_prints.py`: every dev trade (ETH 25M, SOL 10M), copy/fade at the next same-side fill 1–10 s later, after fee, by notional bucket (p99 ≈ $170 ETH, $143 SOL), time left and price | research | copy: −0.6..−1.7¢ (ETH), −0.5..−1.5¢ (SOL) in every size bucket and half; fade: −0.2..−2.8¢. Big prints are slightly better informed than small ones (copy p90–99 −0.6¢ vs <p50 −1.7¢ in Jan–Apr) but never above 0; no time-left × price cell positive in both halves with real n | **Rejected.** Trade size carries ~1¢ of information, less than costs, on both coins. |

## Learnings
- **The market prices the settlement average correctly in the final minute.** Traders evidently watch the CF
  index (or something tracking it better than Binance + basis): the next-fill mid beats a partial-average model
  in log loss at every horizon (at T−30 s 0.16 vs 0.25 on ETH), and the "spot crossed the strike against the
  accumulated average" case isn't systematically mispriced.
- Binance 1 s + basis tracks the CF 60 s settlement average to ~0.2 of a 1-minute move (fat tails; 98.5%
  outcome sign agreement). Some backfill markets have broken strikes (K near 0); filter |K/ev − 1| < 5%.
- No late-window favourite-longshot bias for takers; no information in Kalshi trade size (copy and fade both
  lose about fee + spread).
- The passive side of Kalshi trades earns a small positive amount on average (underdog sales +1..+2¢ at
  6–15 min before close), which led to `strategies/dog-seller/`.
- Kalshi ETH/SOL volume in May–Aug is ~4× Jan–Apr; several screens flip sign between the halves, so
  require both halves (and both coins) before believing anything.

## Current status
- Stage: **rejected at research** (hypotheses 1 and 2). No pipeline runs. Data (trades dump, last-minute table)
  is in `research/data/settle-lockin/` (gitignored), rebuilt by the scripts here.
