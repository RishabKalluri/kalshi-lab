# SOL Order Flow

Markets: KXSOL15M (Kalshi 15-minute SOL up/down; YES if the 60s average of the CF SOL index before close is
at least the 60s average before open).

## Hypothesis (written before any test)
- **Why the market should be mispriced:** aggressive (taker) order flow on the venues where SOL price is
  actually discovered (OKX perpetuals, Binance spot) leads short-horizon price moves: a minute of one-sided
  taker buying is followed by further drift in the same direction over the next few minutes (order-flow
  imbalance / price-impact persistence, Cont-Kukanov-Stoikov 2014; Kyle-style informed flow). Kalshi SOL
  traders quote off the *price* (spot vs strike, time left), not the flow, so at a fixed checkpoint the
  YES price reflects where spot is, not where the flow says it is going.
- **Who is on the other side:** Kalshi SOL participants (about 1/3 of ETH's volume, thin books, ~13 contracts
  at the best price) who price the 15-minute binary from spot distance alone, and slow makers whose quotes
  lag spot.
- **What would prove it wrong:** (1) trailing flow imbalance has no predictive power for the spot move to
  settlement beyond the trailing price return (it's just momentum, which the market may already price);
  (2) it predicts spot but the Kalshi price already moves with it (no edge at the next taker fill after
  fees); (3) walk-forward months mostly negative.

## Plan
1. Screen (development data only, close < 2026-08-20): join per-second SOL flow (OKX perp + Binance spot)
   to the research dataset at fixed horizons; regress the future move (and outcome vs market mid) on
   trailing flow imbalance controlling for the trailing return. Check edge at `next_ask/next_bid` after fees.
2. The engine does **not** replay flow and the recorder doesn't stream it live, so if the screen is
   promising a real test needs infrastructure (see "Infrastructure needed").

## Ideas and prior work used
- `strategies/IDEAS.md`: "Order-flow pressure before checkpoints".
- `strategies/eth-volfav/`: fixed checkpoints (first-crossing entries buy spikes that reverse), taker at ask.
- `research/build_dataset.py` for the per-(market, horizon) table.

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-01 | data check | — | **SOL flow not downloaded** (only ETH: Binance Dec–Sep, OKX Dec–Jan only). | Proxy with ETH flow; ask user for SOL flow. |
| 2 | 10-01 | `flow_screen.py`: ETH flow (Binance imbalance/signed volume 30–300s) vs SOL 15m, 20.6k markets Jan 9–Aug 19 | research | corr with future SOL spot move ≈ 0 (\|r\| < 0.03, own returns slightly mean-reverting) | Flow doesn't predict the spot move to settlement. |
| 3 | 10-01 | `flow_incremental.py`: y ~ logit(mid) + logit(spot model) + flow | research | flow t ≈ +2..+6 vs the *trade-implied* mid, but the trailing return is just as strong | It's stale last-trade mids, not information. |
| 4 | 10-01 | taker at the **next real fill** after fees, top/bottom 10% of signal, Jan–Apr thresholds | research | every signal loses: Binance imb30 −1.6¢ (test, n=14k), flow ⊥ own return −0.7..−1.3¢, spot-staleness model−mid −1.6¢ | Kalshi's next fill already prices the flow. |
| 5 | 10-01 | deciles (`flow_deciles.py`) | research | no decile above 0 for either side; baseline −1.8 / −2.2¢ (fee + spread) | At most ~1¢ of information, less than costs. |
| 6 | 10-01 | extreme bursts (top/bottom 2%, 0.5%) | research | *following* bursts −3..−5¢ (worse than baseline); *fading* ≈ 0, flips sign between Jan–Apr and May–Aug | Mild overreaction to bursts, but not tradable, not robust. |
| 7 | 10-01 | same-coin control: ETH flow vs KXETH15M (22k markets) | research | same picture: every signal −1..−2¢ at fills, no positive decile | The flow idea fails even on the coin whose flow we have. |

No pipeline runs: the engine can't replay flow, and the screen gives no reason to ask for that work.

## Learnings
- **Spot order flow doesn't predict the 15-minute settlement move.** Binance taker imbalance and signed volume
  (30 s to 5 min windows) have |corr| < 0.03 with the standardized move to settlement, for SOL and ETH.
- **Kalshi isn't slow to react to flow either.** Against the *last-trade* mid, flow looks significant
  (t up to 6), but that's because last-trade mids are stale. Against the next real taker fill, every flow
  signal loses about the fee plus spread (≈ −2¢), the same as trading at random.
- **Big flow bursts are, if anything, over-priced:** following the top 2% signed-volume bursts loses 3–5¢,
  worse than random. Fading them comes out ≈ 0 and flips sign between halves, so there's nothing to trade.
- **Screening tip:** in `research/data/*.parquet`, any feature that tracks recent price changes will "predict"
  `y − mid`, because `mid` comes from the last trades. Test against `next_ask/next_bid` (real fills) instead.

## Infrastructure / data notes
- **SOL order flow isn't downloaded**, even though reference.md says it is from Dec 2025. Only ETH has it,
  and ETH's OKX perp flow stops at Feb 1. Before I read the guard rule that downloads are user-only, I started
  a laptop-only download of SOL flow (direct script, public archives, dates before the lockbox). I stopped it
  when I saw the rule. Partial files are left in `~/kalshi-data/backfill/flow/binance_solusdt`
  (Jan 8–Feb 19) and `okx_solusdtswap` (Jan 8–22). Nothing in this analysis used them.
- To test SOL's own flow: `kalshi-lab backfill --series KXSOL15M --only flow --start 2026-01-08` (user/main
  session). Given the ETH same-coin result, I'd give this low priority.
- Trading on flow would also need a live recorder stream and engine replay (see reference.md).

## Current status
- Stage: **parked at research** (no pipeline test). ETH flow as a proxy for SOL, and ETH flow on ETH's own
  market, both show no edge at real fills. SOL's own flow hasn't been tested (no data).
- Next step: none recommended. If SOL flow gets downloaded, run `research/flow_screen.py KXSOL15M sol`
  (needs a `sol` source; the scripts take the coin as an argument) and the decile check. Only continue if a
  decile is clearly above 0 at real fills in both halves.
