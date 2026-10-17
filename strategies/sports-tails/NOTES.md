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
