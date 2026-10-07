# BTC Late-Confirmed Reversal (folder btc-midrev)

Markets: KXBTC15M (Kalshi 15-minute BTC up/down; YES if the 60 s average of the CF BTC index before close is at
least the 60 s average before open).

Why BTC: it's the one 15-minute crypto market where the late-confirmed reversal hasn't been tested in Kalshi prices.
BTC's market is the most efficient, so this is also the hardest test of the boundary-burst story.

## Hypothesis 1 (written before any test): eth-midrev's late-confirmed reversal, transferred to BTC
- **Starting point:** eth-midrev found that the 15-minute reversal lives at window boundaries, and that the part which
  didn't decay is the *late-confirmed* move: the previous window moved |z15| > 1.5 and its last 5 minutes ran
  |z5| > 1.5 the same way. ETH walk-forward +5.4¢, lockbox pass; SOL research +7.7/+9.7¢. In eth-midrev's
  `boundary_shape.py`, BTC's 5-minute move into the boundary flips 55%/56% (A/B), close to ETH's 57%/59%.
- **Why mispriced:** the burst into the boundary (candle-close traders, hedgers of 15-minute binaries rebalancing into
  expiry) overshoots and gives some back after the open; the opening price treats the new window as a coin flip.
- **Who loses:** opening takers and quoters pricing BTC's next window as driftless.
- **Known tension:** eth-overreact found BTC's market has *nearly priced* the plain z15 reversal since May. The
  late-confirmed subset may be priced too.
- **Rule fixed in advance (no BTC tuning):** eth-midrev's `LateConfirmed` exactly: |z15| > 1.5, |z5| > 1.5 same sign,
  first of h = 870/840/810/780 s with mid in 30–70¢, buy the reversal side at the touch, hold to settlement.
- **Wrong if:** in research at next real fills after fee, the late-confirmed fade isn't positive in both halves
  (Dec–Apr, May–Aug 19); or the engine's full walk-forward isn't promising; or the lockbox loses.

## Hypothesis 2 (written before any test): the market-wide burst reverses on BTC; a BTC-only burst doesn't
- **Mechanism:** a burst that hits BTC, ETH and SOL together into the boundary is market-wide flow (index/basket
  hedges, liquidation cascades across perps, 15-minute binary hedgers on several coins) and should overshoot most.
  A BTC-only burst is more likely information (BTC-specific news/flow) that sticks. BTC's market prices BTC's own
  move; it doesn't check whether the whole market moved with it.
- **Rule fixed in advance:** basket z = equal-weight mean of BTC, ETH and SOL z15 (and z5), each in its own rv_60m
  units. Trigger on BTC: |Z15_basket| > 1.5 and |Z5_basket| > 1.5, same sign, and BTC's own z15 the same sign; fade
  on KXBTC15M at the same checkpoints/mid range as H1.
- **Wrong if:** at next real fills after fee it isn't positive in both halves; or it's no better than H1's BTC-only rule
  on the same period; or BTC-late-confirmed rows *without* a basket move do as well (then it's not the market-wide part).
- **Data:** needs ETH and SOL spot at trade time. The engine replays spot for the series a strategy lists; if it can
  only list KXBTC15M, this needs an engine option (report rather than build if it touches defaults).

## Ideas and prior work used
- `strategies/eth-midrev/` (rule, strategy.py, `research/late_move.py`, `boundary_shape.py` BTC numbers).
- `strategies/eth-overreact/` (panel builder `research/panel.py`, BTC control: the plain reversal nearly priced on BTC).
- `strategies/settle-lockin/research/trades_dump.py` (Kalshi trades with aggressor side).

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-07 | v1 = eth-midrev `LateConfirmed` unchanged (strategy.py also carries a default-off `basket` filter for H2 and trades only `trade_series`) | smoke | passed (2 markets) | mechanics ok |
| 2 | 10-07 | v1 (job btc-midrev-1006-230654) | quick | passed: −13.8¢/ct, CI −31.4..+5.2, 27 markets, 0/3 days | noise-level sample; screen all dev months before spending a full test |
| 3 | 10-07 | `research/trades_dump_par.py` + `research/open_panel.py` (BTC's 179M trades don't fit the old single-process tools; same definitions, h = 870–780 only) and `research/late_screen.py` (**H1**, **H2**). Method check on ETH: late-confirmed +6.50/+4.44¢ vs eth-midrev's +6.3/+5.1 | research | **BTC H1 late-confirmed: +6.21 (se 1.9, n 648) / −2.31 (se 1.8, n 704)**; May −1.2, Jun −3.3, Jul +0.7, Aug −6.1. **H2 basket: +7.59 (se 2.5, n 367) / +2.91 (se 2.5, n 374)**, 7/8 months positive (Jun −0.3). H1 & basket +7.91/+3.05; **H1 without basket +4.56/−7.04**; plain z15 control +2.94/−0.70 | **H1 rejected** (decayed in May–Aug, like the plain reversal on BTC). **H2's split holds as stated in advance**: market-wide bursts reverse, BTC-only bursts stick (−7¢ in B). Go to the engine with `basket=1`. |
| 4 | 10-07 | v2 = H2: `basket=1`, config series BTC+ETH+SOL (ETH/SOL only feed spot; `trade_series` = KXBTC15M) | smoke | **failed: no fills** in the 6 h smoke window | The basket trigger fires ~3×/day; the smoke window just had none. |
| 5 | 10-07 | v2 ad-hoc Jun 1–15 (dev) | ad-hoc | 39 BTC markets traded, **all 39 among the research rule's 49** for those dates (the rest skipped on book/mid), +0.9¢/ct on 702 contracts | Mechanics verified (it trades the research markets, BTC only), so quick runs with `--skip-smoke`. |
| 6 | 10-07 | v2 (job btc-midrev-1007-003420) | quick | passed: +0.92¢/ct, CI −28.1..+27.7, 12 markets, 2/3 days | noise-level; go to full |
| 7 | 10-07 | v2 (job btc-midrev-1007-003635; ~10 h, three series loaded per month, laptop on battery) | **full (1/3): inconclusive** | **+3.50¢/ct, CI −0.56..+7.51**, 11.7k contracts, 596 markets, **6/8 months**: Jan +5.9, Feb +4.5, Mar +4.1, Apr +9.7, May +3.9, **Jun −0.6, Jul −1.0**, Aug +3.3; **2× latency Jun–Aug +1.10¢ (CI −5.3..+7.5)** | Same shape as research (A +7.6, B +2.9): real early, fading to noise by summer. Jun–Aug engine avg ≈ +0.5¢. No threshold changes (that would be fishing in a decaying signal). |

## Hypothesis 3 (written before screening it): perp-driven bursts overshoot; spot-driven ones don't
- **Mechanism:** a late burst pushed by perpetual-swap takers (leveraged flow, stop-outs, liquidations) is forced
  trading that overshoots and gives back; a burst led by spot buyers/sellers is more often real demand. The H1/H2 rules
  can't tell them apart. If the reversal lives in perp-driven bursts, conditioning on it should restore the May–Aug edge.
- **Measure (fixed in advance):** OKX BTC perp taker imbalance over the 300 s before the open,
  imb = (buy − sell)/(buy + sell), signed by the late move; "perp-driven" = signed imb above its median among the rule's
  triggers. Split H1 (BTC late-confirmed) and H2 (basket) triggers into perp-driven vs not; fade PnL at next fills.
- **Wrong if:** the perp-driven half isn't better than the other half in *both* halves of development data, or isn't
  positive in May–Aug. **Even if right**, live use needs the OKX flow streamed by the recorder and replayed by the
  engine (infrastructure the user must approve), so a pass here is a report, not a pipeline run.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 8 | 10-07 | `research/perp_driven.py` (**H3**): split H1/H2 triggers at the median signed OKX perp taker imbalance (300 s before the open) | research | H1: perp-driven +3.70/−2.74 vs rest **+8.60**/−1.86; H2: perp-driven +4.51/+2.40 vs rest **+10.69**/+3.41 (A/B, se 2.6–3.6) | **H3 rejected**, and backwards: bursts with *less* perp-taker pressure reverse more. Doesn't rescue May–Aug either. |

## Learnings
- **BTC's late-confirmed reversal has decayed like its plain reversal:** +6.2¢ Jan–Apr, −2.3¢ May–Aug (research).
- **Market-wide bursts reverse; BTC-only bursts stick.** Among BTC late-confirmed triggers, those where the BTC/ETH/SOL
  basket also burst made +7.9/+3.1¢ (A/B), the BTC-only ones +4.6/−7.0¢. The engine confirmed the basket rule early
  (Jan–May +3.9..+9.7¢/month) but it faded to about zero in Jun–Jul (full: +3.50¢, CI −0.56..+7.51, 6/8 months).
- Bursts with heavy perp-taker pressure reverse *less* than the rest (H3): forced-flow overshoot isn't the mechanism.
- Multi-series configs work for spot-only inputs (list ETH/SOL in `series`, trade only `trade_series`), but every
  month-run then replays all three markets: ~10 h for a full test on battery vs ~1–2 h for BTC alone.
- BTC research tools: the 179M-trade dump needs `research/trades_dump_par.py` (parallel, columnar) and
  `research/open_panel.py` (h = 870–780 only); the old single-process versions don't finish.

## Current status
- Stage: **parked, inconclusive** (full 1/3 used; lockbox not run). H1 and H3 rejected at research; H2 (basket) is the
  best BTC version of the boundary reversal, but its edge faded to ~0 in Jun–Jul, so a lockbox now would mostly test noise.
- If revisited: rerun full on the same code once a few more months of development data exist (lockbox moved forward
  deliberately), to see whether Aug's +3.3¢ was a recovery or noise. Run it while the laptop is on power.
