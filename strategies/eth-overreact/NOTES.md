# ETH Overreaction Fade

Markets: KXETH15M (Kalshi 15-minute ETH up/down; YES if the 60 s average of the CF ETH index before close is at
least the 60 s average before open).

Why ETH: eth-volfav showed ETH's 15-minute market is the one with a measurable (vol-level) inefficiency, BTC's is
efficient, and SOL's version of the same edge failed the lockbox. ETH is deep enough to trade but thinner than BTC.

## Hypothesis 1 (written before any test): the market overreacts to its own recent price moves
- **Why the market should be mispriced:** every "our fair value vs the price" model lost to the market on ETH
  (settle-lockin, btc-anchor-vol, sol-vomma), because our Binance + basis *level* of the CF index is noisier than
  what traders see. But *changes* in Binance spot over 30–120 s track changes in the CF index almost exactly. So a
  market-relative test is possible: given the price a minute ago and the spot move since, how far *should* the
  price have moved (a delta update at the market's own vol)? sol-flow found that following big flow bursts loses
  3–5¢/contract at real fills, worse than the −2¢ of random trades: a hint that the Kalshi price overshoots after
  sharp moves. If Kalshi's price moves further than the spot move justifies (momentum chasing, takers sweeping a
  thin book), the next real fill is mispriced against the move; if it moves less (sticky quotes), with it.
- **Who is on the other side:** retail takers chasing a move ("it's running, buy YES") through a thin book, and
  makers who widen/step back after a jump, leaving the price set by the chasers.
- **What would prove it wrong:** at real next fills (`next_ask`/`next_bid`, after the taker fee), fading (or
  following) the gap between the market's price move and the spot-justified move is ≤ 0 in both halves of
  development data (Jan–Apr, May–Aug 19), or only positive in one; or the walk-forward months are mostly negative.

## Ideas and prior work used
- sol-flow (burst-following loses more than random), settle-lockin / btc-anchor-vol / sol-vomma (level models lose
  to the market; screen at next real fills, never the last-trade mid), eth-volfav (fixed checkpoints).
- Trades dump `research/data/settle-lockin/KXETH15M_trades.parquet` (every development trade with aggressor side).

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-01 | `research/panel.py` (22.4k markets × 29 checkpoints from the trades dump + Binance 1 s) and `react_screen.py`: gap = market Δz over the last 30/60/120 s minus the spot-justified Δz (delta update at rv_15m), deciles cut on Jan–Apr, PnL at next real fills after fee | research | corr(market Δz, spot Δz) 0.84–0.91. Deciles monotone the *under*-reaction way (low gap → buying YES best), but the best cells are −0.2..−1.1¢ (lag 60), 0.0..−1.0¢ (lag 30), +0.1..−0.8¢ (lag 120); spread best–worst ≈ 2.5¢, i.e. ~1¢ of information per side vs ~2¢ of costs. No overshoot to fade | **Hypothesis 1 rejected.** Kalshi ETH doesn't overreact to spot moves; it lags slightly, by less than fee + spread (the sol-flow staleness result again). |
| 2 | 10-01 | `streak_round.py`: H2 streaks (early window, h 480–840) and H3 round levels ($25/$50/$100 between spot and strike, favourite PnL by price bucket) | research | **H3 wrong way**: with a round level in between, the favourite does ~2¢ *worse* (0.65–0.85 buckets, both halves), and the underdog side is still below costs. **H2**: outcomes mean-revert (P(up \| prev down) 51.9%, P(up \| prev up) 47.4%); after 3–4 DOWNs, YES at next ask +2.9/+4.8¢ (Jan–Apr) but −1.3/−0.5¢ (May–Aug) | H3 rejected. Streak *count* isn't it, but the reversal is real: look at the size of the previous move. |
| 3 | 10-01 | `prev_move.py`: by previous window's move z = (A_n − A_{n−1}) / (rv_60m·30), A = 60 s Binance average at each boundary | research | ETH: after z < −1.5, P(up) 55.1/56.1% (A/B) while the first-1.5-min mid is 49.7/52.1¢; YES at next ask +4.1/+1.9¢. After z > 1.5: P(up) 43.0/46.0%, mid 49.0/48.4¢, NO +4.0/+0.3¢. Effect fades later in the window (prices catch up by h 180–450). **SOL** same: +9.9/+2.6¢ and +6.7/+3.7¢ | Gambler's-fallacy framing was wrong (count doesn't matter), but there's a magnitude-driven reversal the opening price ignores. |
| 4 | 10-01 | `reversal_stats.py`: Binance-only sign autocorrelation of consecutive 15-min returns per coin and month; simple fade by month (first 1.5 min, 30–70¢, \|z\|>thr, next fill, fee) | research | sign corr −0.02..−0.09 **in every month for BTC, ETH and SOL** (linear corr ≈ 0); P(opposite \| big move) 55.3% BTC, 56.6% ETH, 57.4% SOL. ETH fade \|z\|>1.5: **+2.18¢, t(market) 2.5**, Jan 7.7, Feb 5.5, Mar 5.1, Apr 1.3, May 1.5, Jun 1.6, Jul −0.4, Aug 1.4. SOL +5.6¢, t 4.0 | Real spot fact, not a Kalshi artifact; the ETH market has partly learned it since May. → Hypothesis 4. |
| 5 | 10-01 | `fit_screen.py`: one-parameter model fair = logistic(logit(mid) + b·clip(z)), b fit on Jan–Apr (−0.14), trade May–Aug when fair − next ask − fee > margin | research | **−1.1¢ ± 1.0** at every margin (0–3¢), ~9k markets; log loss no better than the mid | A linear-in-z model trades small \|z\| (no edge there: the effect is convex) and selects on noisy price gaps (fair − ask), which is adverse selection. Use a plain threshold on \|z\|, no fair-vs-ask test. |
| 6 | 10-01 | `diag.py`: z from strikes (ΔK) vs Binance averages; threshold fade, all rows vs first trigger per market | research | corr(zK, zB) 0.998. ΔK fade, first trigger: \|z\|>1.0 +2.6/+0.7¢ (A/B), **\|z\|>1.5 +4.8/+1.6¢**, \|z\|>2.0 +6.0/+1.9¢ (609/757 markets) | Effect grows with \|z\|; 1.5 keeps enough markets. `by_price.py`: no clean dependence on the entry price, so no price filter. |
| 7 | 10-01 | strategy v1 (`ReversalOpen`): \|z\|>1.5 from strikes, checkpoints h 870/840/810/780, mid 30–70¢, IOC at the touch, once per market | ad-hoc Jun 1–15 | −4.35¢/ct, 168 markets, 3,050 ct, t −1.1 | Engine picks the same markets as the research (168 of 192, none extra) and the research also says −0.8¢ for these two weeks: a weak stretch, not a bug. |
| 8 | 10-01 | v1 | smoke | passed (2 markets) | mechanics ok |
| 9 | 10-01 | v1 (job eth-overreact-1001-175106) | quick | passed: −1.96¢, CI −17..+13, 46 markets, 1/3 days | noise-level, go to full |
| 10 | 10-01 | v1 (job eth-overreact-1001-175153) | **full (1/3): promising** | **+2.23¢/ct, CI +0.37..+4.10**, 53.7k contracts, 2,698 markets, **8/9 months positive** (Dec +15.0 n=6, Jan +5.6, Feb +4.2, Mar +5.2, Apr +1.8, May +1.3, Jun +0.4, Jul −1.2, Aug +2.5); 2× latency Jun–Aug +0.89¢ (CI −2.4..+4.1); max drawdown $274 | Matches the research month by month. The edge decays: Jan–Mar ~5¢, May–Aug ~+0.8¢. The lockbox (Aug 20 on) is the honest test of whether anything is left. |
| 11 | 10-01 | v1 (job eth-overreact-1001-190803) | **lockbox: pass** | **+2.21¢/ct, CI −2.05..+6.50**, 10.3k contracts, 502 markets, 21/42 days; Aug 20–31 −2.0¢ (127 mkts), **Sep +3.5¢** (375), recorded books Sep 29–Oct 1 −17.6¢ (25 mkts, CI −34..+1.4) | The recorded-book loss is the outcomes (36% win rate; the backfill run lost −13.8¢ on the same overlapping markets), not execution: real-book fills were ~1¢ worse on our side, about what `slip_c=1` costs. Pass, not strong pass. |
| 12 | 10-01 | `paper-start` (rv_scale=1.09, slip_c=1, 0.5%/order) | paper | started on the server as kalshi-paper@eth-overreact | |

## Hypothesis 2 (written before the screen): gambler's fallacy / hot hand across windows
- **Why mispriced:** Kalshi shows recent results of the series; retail traders reading a streak (three UPs in a
  row) bet on reversal (gambler's fallacy) or continuation (hot hand) early in the next window, when the price is
  near 50¢ and only spot vs strike should matter. 15-minute ETH returns have (roughly) no serial correlation, so any
  streak-dependent tilt of the early price is a mispricing.
- **Who loses:** early-window takers betting on the pattern.
- **Wrong if:** at h ≥ 480 s, YES and NO PnL at next real fills, after fee, by prior streak (length and direction)
  and by the previous window's move size, is ≤ 0 everywhere or not the same sign in both halves.

## Hypothesis 3 (written before the screen): round-number levels act as barriers the market doesn't price
- **Why mispriced:** ETH spot around round levels ($50/$100) shows support/resistance (resting liquidity and options
  pinning cluster there). If a round level sits between spot and the strike, the underdog needs spot to break
  through it, which happens less often than a Gaussian move suggests; the market, pricing spot distance, overprices
  the underdog.
- **Who loses:** underdog buyers (already the losing side of the favourite-longshot bias) in exactly these spots.
- **Wrong if:** favourite PnL at next fills, after fee, isn't higher when a round level lies between spot and
  strike than when none does, in both halves.

## Hypothesis 4 (written after the H2/H3 screens, before any model fit or pipeline run): fade the previous window's big move at the open
- **Why mispriced:** 15-minute crypto returns have a small but persistent *sign* reversal (every month, all three
  coins): after a large move the next 15 minutes go the other way ~55–57% of the time. Mechanism: liquidation
  cascades and inventory-driven overshoots on perps that partly unwind. The Kalshi price at the open of the next
  window anchors on "a fresh coin flip" (~50¢) and only prices spot vs strike, not that drift.
- **Who loses:** takers who treat each window as independent, or chase the continuation (hot hand) right after a
  big move; makers quoting 50¢ ± spread at the open.
- **Design:** previous move z = (K_this − K_prev) / (rv_60m · √900), with K the strikes (each window's strike is the
  previous window's CF settlement average, so ΔK is the previous window's move in CF terms, no basis error). At
  fixed checkpoints in the first ~1.5 minutes, fair = logistic(logit(mid) + b·clip(z)), b fit by `fit()` on earlier
  data; buy the reversal side at the ask when fair − ask − fee > a margin.
- **Wrong if:** fit on Jan–Apr, the rule loses on May–Aug at next fills; or the walk-forward is < 60% months
  positive / CI ≤ 0; or the lockbox (Aug 20 on) loses, which would mean the market finished learning it.
- **Known risk:** decay. Jan–Mar made 5–8¢, May–Aug ~1.5¢ on ETH. The lockbox is the honest check.

## Learnings
- **15-minute crypto returns reverse in sign after big moves**, every development month, on BTC, ETH and SOL (sign
  autocorrelation −0.02..−0.09; ~56% reversal after |z| > 1.5), while the linear return autocorrelation is ≈ 0. The
  Kalshi price at the open of the next window ignores it on ETH/SOL; BTC's market has nearly priced it since May.
- **The effect is convex in |z|**: nothing below |z| ≈ 1, +2..+6¢ above 1.5–2. A linear-in-z fair-value model loses
  (it trades small z and selects on noisy price gaps); a plain threshold works.
- **ΔK (strike to strike) is the previous window's move in CF terms**; it matches Binance 60 s averages (corr 0.998)
  with no basis error. Useful for any strategy that needs the last settlement.
- **The edge is decaying on ETH**: ~5¢ in Jan–Mar, ~+0.8¢ May–Aug in the walk-forward, +2.2¢ in the lockbox (Sep +3.5¢).
  SOL's version is about twice as large (research: +5.6¢, t 4.0) and hasn't been tested in the engine.
- No edge from: overreaction to spot moves (the market lags slightly, < costs), streak counts, round-number barriers
  (the favourite does *worse* with a round level in between; the underdog side is still below costs).

## Current status
- Stage: **parked** (paper ran Oct 1–7, stopped at the user's request to free a paper slot). Full test 1/3 used; lockbox spent (pass).
- Why: superseded by `eth-midrev`, whose trades are a subset of this strategy's (same market, same side). The trades
  unique to this strategy (last 5 minutes not confirming the move) are the ones that decayed since May.
- Restart only if eth-midrev fails in paper. The SOL follow-up was done as `sol-midrev` (late-confirmed rule).
