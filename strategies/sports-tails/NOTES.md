# Sports extremes maker

Markets: KXNBAGAME, KXNHLGAME.  source: books.  derived_from: pregame-maker (same engine/quote code, tails=1).

## Hypothesis (written before the pipeline runs)
- Pre-game touch quoting at mid prices dies on the maker fee (pregame-maker). At the extremes the fee is 0.0175*p*(1-p) ~ 0.14c
  while the tick is still 1c, so a bid on a >=90c favourite / offer on a <=10c longshot keeps the spread plus whatever
  favourite-longshot effect exists. Danger: comebacks pick off these quotes (score-feed traders). Protection: pull the side after a 2c mid move in 5 min.
- Wrong if the pooled walk-forward CI net of maker fee is <= 0 or the lockbox loses.
- Parameters fixed a priori (not tuned on results): tail_px=100, pull_move=20 mills in 300 s, cooldown 600 s, qty 20, max_pos 100, per-game cap 200,
  quoting from 6 h before the estimated start (expected_expiration - 171 min) through the game.

## Evidence before the pipeline (ad hoc engine runs on development months, books source, `--timeline-s 0`, back of queue, 150 ms)
Net = engine pnl minus the exact maker fee per fill (engine charges makers 0; fee is only ~0.14c here). CI = bootstrap over games.
| window | fills | contracts | gross | net | CI95 (games) |
|---|---|---|---|---|---|
| Jan 7-Jan 31 | 2,766 | 42.1k | +1.87c | +1.72c | -1.05..+4.14 |
| Feb | 1,788 | 25.6k | +0.54c | +0.40c | -3.50..+3.75 |
| Mar | 2,958 | 44.7k | +3.44c | +3.30c | +1.34..+4.92 |
| Apr | 2,511 | 39.5k | +0.10c | -0.04c | -3.10..+2.76 |
| May | 561 | 8.5k | +1.93c | +1.79c | -4.84..+7.17 |
| Jun | 68 | 1.1k | -19.8c | -19.9c | 8 games |
| **pooled** | 10,652 | 161.5k | +1.51c | **+1.37c** | **+0.03..+2.65** (1,015 games, 4/6 months positive) |
- 2x latency (300 ms), Mar-May: +1.73c (CI -0.09..+3.31) vs +1.74c at 150 ms: the strategy is slow.
- NBA +1.27c [-0.55, 2.93]; NHL +1.49c [-0.65, 3.38]. Sells (offer longshots) +1.75c [0.31, 3.04]; buys (bid favourites) +0.95c [-0.61, 2.31].
- By price: offers at 0-3c +1.1c, 3-6c +2.2c, 6-10c +1.7c; bids at 91-94c +1.2c, 94-97c +2.5c [1.0, 3.8], 97-100c +1.9c; **bids at exactly 90c (and 91)
  -1.2c** (the weak spot; trade-level screens agree: NBA takers paying 90-94c win 2.6c more than price in the event-average). Not tuned
  away: tail_px=60 would be a tuned v2 and must go to a new folder/lockbox.
- By game phase (fraction of the game elapsed): pre-game +5.1c (54 games), Q1 +1.8, Q2 +3.1, Q3 +0.7, Q4a(75-90%) -1.1 (NBA -3.5), last 10% +3.9: broad, not one segment.
- Pull ablation (Mar): without the momentum pull +3.13c vs +3.30c with it: the pull is not the source; the edge is the extremes carry.
- Mid-markout of the fills is negative (-0.08c at 60 s, -0.40c at 300 s): this is not spread capture, it is carry to settlement.
- Caution: trade-level screens (contract-weighted, all trades) show in-game takers buying 6-10c contracts winning +3c (makers selling them lose),
  while the event-averaged view shows takers paying 6-10c losing 3.9c; the sim's small, queue-delayed fills sit in the second regime.
  Real fills (paper) should check this.

- **Payoff shape (research/pergame.py, Jan-Jun, 1,015 games):** pennies in front of a steamroller. 94.4% of games win $2-20 (qty 20 quotes, max
  200 contracts per game), 5.6% lose up to -$190 (a full capped position on the wrong side of a comeback/upset). Total +$2,212 (mean +$2.18/game);
  the worst 10 games (1%) lost $1,900, i.e. 86% of the net; without the best 1% the net is still +$2,011. The CI above captures this, but a
  lockbox/paper stretch with 2-3 extra upsets can erase months of carry. Sizing must be small (the per-game cap, not the qty, sets the loss).

- **Stop-loss variant (param `stop`, default off; motivated by the payoff shape above, run before any pipeline result):** exit with an IOC at the touch
  when a position is 10c under water, then stop quoting that market. March: net **-0.20c** (CI -1.43..+0.92) vs +3.30c without; the weak-spot bids at
  90c fall to -8.7c. Dips of 10c on a 90c+ favourite mostly recover, so stops turn recoverable drawdowns into realized losses (plus the 7% taker fee).
  Dropped; the tail is managed by the per-game cap/size instead.
- **Sensitivity (Jan, tail_px=60 i.e. only >=94c bids / <=6c offers):** +1.41c (CI -0.79..+3.21) vs +1.72c at tail_px=100: not sensitive to the band.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-16 | v1 smoke | smoke | 0 orders (window Aug 31 has no games); job then failed with PermissionError because my new folder was not group-writable (fixed with chmod g+w) | smoke can't test sports in the off-season |
| 2 | 10-16 | v1 full queued (job sports-tails-1016-010959) | full | **failed within ~2 min, no month finished, no ledger record** (3 parallel months of NBA+NHL books with the 5 s engine timeline: 13 GB/month vs the 6 GB sandbox, very likely OOM) | needs the engine/pipeline change in research/infra_requests.md |
| 3 | 10-16 | v1 quick (job sports-tails-1016-011438) | quick | 0 trades (Aug 29-Sep 1 has no NBA/NHL games) -> "rejected at quick" with pnl 0 | mechanical: this window can't evaluate sports; ignore the verdict |

## Learnings
- The pipeline's monthly sports-books runs need ~13 GB with the engine's chart timeline: if the full crashes, that is why (see report Requests).
- Per-contract edge is small (+1.4c) but the volume is big; contracts are 20 per quote here only to keep the research simple; the real size is the sizing policy.

## Current status
- Stage: full test queued/running; no lockbox yet (lockbox needs a promising full).

## Rerun (agent run 20261021-0058-2)
Picked up as the next untaken testable item after the SOL screens: books pipeline no longer keeps the chart timeline (commit f2ef70b), so full 1/3 requeued, rule unchanged (job sports-tails-1021-011103).
| 4 | 10-21 | v1 unchanged, full 1/3 (job sports-tails-1021-011103, books pipeline without timeline) | full | **inconclusive (mechanical)**: pooled +1.37c/ct, CI +0.36..+2.36, 1,801 mkts, $+2,212, 98/136 days positive. Months: Jan +1.70, Feb +0.40, Mar +3.28 (CI +1.8..+4.7), Apr -0.04, May +1.79, Jun -19.9 (11 mkts), Jul/Aug 0 mkts (off-season, books have no games). 4/6 months with games positive, 4/8 counting empty ones. POOLED-lat2x covers only Jun-Aug (11 mkts, -20c), so the 2x-latency gate fails for lack of games, not evidence | the pooled CI is above 0 on 1,801 markets, but the gate cannot pass: empty summer months and a latency run restricted to them. No lockbox (verdict not promising); 2 full tests left. A re-run would give the same verdict unless the latency run covers months with games. Needs the user/maintainer to decide whether to accept this as evidence (e.g. a lat2x run on Jan-May), or wait for the Oct-Nov games to become development data. |

### Full-run decomposition (fills of wf-2026-01..06, per-fill gross PnL to settlement minus fee; not a new test)
NBA bids +1.32c / offers +1.22c per contract; NHL bids +0.51c / offers +2.40c. By price: bids 900-940 +0.8c, 940-970 +2.5c, 970-1000 +1.9c; offers <=30 +1.1c, 30-60 +2.2c, 60-100 +1.7c. Edge appears on both sides and both sports (not one bucket), which supports it being real; Mar carries most of the dollars. EPL/NFL books are too small (EPL ~80 games Jan-May; sibling logic assumes 2-way markets) to extend the rule.

### Spin-off screen: same extremes idea on weather (ad hoc, wx-maker code, books, NY+CHI, 2-week slices Mar 10, May 10, Jul 10)
Bids on brackets >=90c (min_mid=900): -6.7 / -1.2 / -0.5 $ per traded market (t -0.9, -0.3, -0.1). Offers on brackets <=10c (min_mid=5 max_mid=100): -3.7 / +0.7 / +0.6 $ (t -1.4, +0.5, +0.4). Nothing; weather quoting is dead at the extremes too (no fee advantage there, adverse selection from observations). Not escalated.

### 2x-latency check on game months (ad hoc, 300 ms, books, NBA+NHL, rule unchanged; the pipeline's lat2x only covered the empty Jun-Aug)
Jan +1.74c/ct (t 1.8), Feb +0.43c (t 0.3), Mar +3.27c (t 4.4) vs normal latency in the full test +1.70 / +0.40 / +3.28. Latency does not matter for this strategy (post-only resting quotes). Ad hoc, not a pipeline record; evidence for the gate decision only.

### Generalisation check (ad hoc, rule unchanged, books, Jan-May)
KXEPLGAME: -3.5c/ct, 74 markets traded, t -1.0 (3-way markets, sibling exposure logic assumes 2-way). KXNFLGAME+KXNFLTOTAL: -4.4c/ct, 15 markets. Too small to conclude, but no support for extending the rule beyond NBA/NHL.

### Game-level robustness of the full run (wf-2026-01..06 markets.csv, games with fills)
1,015 games, total $+2,212, mean $+2.18/game, se $1.08 (t 2.0); game bootstrap 95% CI [+$19, +$4,280]. Not concentrated: top 10 games = 9% of PnL, dropping the best 20 leaves $+1,816. NBA $+2.04/game (552), NHL $+2.34/game (463). Tail risk: the worst 10 games lost $-1,889 together (comebacks against a 90c+ bid or a longshot offer), about 85% of the total profit: a thin edge with a fat left tail.

## v2 (pre-registered before the run): stop=250
Reason from development data (not a lockbox): the worst 10 games lost ~85% of total profit (comebacks). The strategy's existing `stop` param exits via IOC at the touch when a position is 250 mills under water (e.g. a 95c bid bought, price falls to 70c). Expect fewer catastrophic games but taker fee+slippage on the exits; full 2/3 decides. Everything else unchanged.
| 5 | 10-21 | v2 stop=250 (job sports-tails-1021-015853) | full 2/3 | inconclusive: +0.01c/ct, CI -0.75..+0.76, 1,801 mkts, $+25 (v1 +1.37c, $+2,212) | The stop cuts the edge to zero: stopped positions pay the taker fee and the touch slippage and often would have recovered; the left tail is the price of the maker edge. Keep v1 (no stop). 1 full test left. |

## v3 (pre-registered): flow_w=60 (pull the side that one-sided taker flow is hitting)
Reason: the stop (v2) failed because exits are taker trades at the worst moment; the cheaper protection is not to be resting when informed flow arrives. Existing params: flow_w=60 s, flow_thr 0.6, flow_min 500 contracts. Mechanism-based default values, not tuned. Full 3/3 (last one) decides; v1 remains the reference.
