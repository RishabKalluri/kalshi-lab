# Asymmetric Vol (folder asym-vol)

Markets: KXETH15M and KXSOL15M (Kalshi 15-minute up/down; YES if the 60 s average of the CF index before close is at
least the 60 s average before open).

Why ETH and SOL: the user asked for SOL or ETH. These are the thinner 15-minute markets where vol-pricing errors have
been measured (eth-volfav, us-hours-vol); BTC is efficient and serves as a control.

## Hypothesis 0 (quick check, before anything else): SOL's Kalshi quotes lag SOL spot by more than costs
- eth-overreact H1 found ETH's Kalshi price lags spot by less than fee + spread. SOL's market is thinner, so the lag
  could be bigger. Wrong if, at next real fills after fee, no decile of gap = market Δz − spot-justified Δz is positive.

## Hypothesis 1 (written before screening it): the vol response to a move depends on its sign, and Kalshi ignores the sign
- **The vol fact to check:** in equities, vol rises after falls and drops after rises (the leverage effect; Corsi &
  Renò 2012 asymmetric HAR). In crypto the sign is debated (some periods show an *inverse* effect: vol up after
  rallies, FOMO/short squeezes). Either way, if future 15-minute vol depends on the *sign* of the recent move beyond its
  size, a vol estimate built from unsigned trailing realized vol is biased in a signed way.
- **Why the market should be mispriced:** Kalshi's 15-minute price, read as an implied vol, tracks trailing realized
  vol (eth-volfav, us-hours-vol: iv follows rv_5m/rv_15m). Unsigned trailing vol treats a 1% drop and a 1% rally the
  same. If vol after drops is (say) 20% higher than after rallies, then in a window where spot has fallen below the
  strike, the YES underdog is underpriced (more vol to come than priced); where spot has rallied above the strike, the
  YES favourite is underpriced (less vol than priced). Both point the same way: YES cheap after moves under a leverage
  effect, NO cheap under an inverse one.
- **Who is on the other side:** takers and quoting bots pricing the remaining move at trailing vol without a sign term.
- **Not the same as eth-volfav:** eth-volfav buys the favourite whenever iv ≫ an unsigned HAR forecast. This trades
  the sign-dependent part, which can mean buying the underdog, and should be checked for overlap.
- **What would prove it wrong:** (1) in Binance 1 s, signed trailing returns don't predict log rv over the rest of the
  window beyond log rv_5m/15m/60m/4h (coefficient insignificant or flips between Jan–Apr and May–Aug); (2) the market's
  log(iv / rv_fut) does not vary with the signed move in the same direction; (3) buying the side the sign favours at the
  next real fill, after fee, isn't positive in both halves on ETH and SOL.

## Hypothesis 2 (written before screening it): SOL's *own* order flow predicts SOL's move
- sol-flow tested ETH flow as a proxy (SOL flow wasn't downloaded then) and ETH flow on ETH; both dead. SOL's Binance
  and OKX flow now exist (Dec 2025 on). Thinner coin, maybe more informed flow. Wrong if no decile of SOL's own flow
  imbalance/signed volume is positive at the next real fill after fee. (Research only: the engine can't replay flow.)

## Hypothesis 3 (written before screening it): takers hitting round-priced resting orders win
- Retail places limit orders at round prices (x0¢, x5¢) and leaves them; when fair value moves, those orders go stale
  and takers pick them off. Who loses: set-and-forget limit-order placers. Wrong if taker PnL after fee at round
  prices isn't positive (or at least clearly better than at other prices) in both halves.

## Hypothesis 4 (written after measuring the in-window vol profile, before checking prices): late-window vol is overpriced
- **The fact (window_profile.py):** variance is not spread evenly across the 15-minute window. Normalised by each
  window's own mean, it falls almost linearly from ~1.4× in the first 30 s (2.0× in the first 10 s) to ~0.75× in the
  last 30 s, on ETH and SOL, in both halves and on weekends, with a pulse at the start of every minute (first 10 s of
  each minute ~1.3–1.5×). Remaining variance at h = 300 is 0.28 of the window vs 0.33 for a uniform rate.
- **Why mispriced:** a trader pricing the remaining move from trailing in-window vol uses the noisy early part of the
  window, so late in the window implied vol is too high and favourites are too cheap (~2–3¢ at 70–85¢).
- **Wrong if:** favourite PnL at the next real fill after fee by h × price band isn't positive in both halves.

## Ideas and prior work used
- `strategies/eth-overreact/research/panel.py`, `react_screen.py` (H0), `research/data/<SERIES>.parquet` (research dataset).
- eth-volfav (implied-vol math, HAR forecast), us-hours-vol (iv tracks trailing rv; scheduled vol steps).

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-10 | **H0**: `eth-overreact/research/react_screen.py KXSOL15M 30/60` | research | Every decile negative at both lags: buy YES −0.1..−2.6¢, sell YES −0.8..−3.8¢ (A and B); corr(market Δz, spot Δz) 0.75 (lag 30), 0.83 (lag 60) | **H0 rejected.** SOL's market lags spot a little more than ETH's but still by less than fee + spread. |
| 2 | 10-10 | **H1**: `research/sign_vol.py` (ETH, SOL): log rv_fut ~ HAR + \|z15\|, \|z60\| + signed z15, z60 (one row per market at h = 600); log(iv/rv_fut) by z15 bin; buy/sell YES PnL by z15 bin × h | research | Signed terms ≈ 0: ETH z15 −0.003 (t −0.9) / −0.002 (t −0.4), SOL −0.005 (t −1.5) / −0.009 (t −3.4), i.e. a 2σ move shifts future vol by ~1–2%. Unsigned \|z15\| matters (+0.04, t 6–9). Market iv gap by sign: no consistent asymmetry. PnL: nothing positive except the known open-reversal cells (h 720–840) | **H1 rejected.** No leverage (or inverse-leverage) effect at the 15-minute scale on ETH or SOL. |
| 3 | 10-10 | **H2**: sol-flow's `flow_screen.py` + `flow_deciles.py` copied, run with SOL's own Binance/OKX flow (64k rows, mid 10–90) | research | \|corr\| with future SOL move < 0.012 for every flow feature; baseline −1.8/−2.2¢; **no decile positive** for any feature (best −0.1¢) | **H2 rejected.** Closes sol-flow's open question: SOL's own flow is as useless as ETH's. |
| 4 | 10-10 | **H3**: `research/round_price.py`: every dev taker trade (ETH 20M, SOL 8.4M), PnL after fee by price class (x0 / x5 / other) × band × side × half | research | Takers lose 0.3–3¢ in every cell; round prices no better than others (one SOL cell +0.3/+1.3¢ in A, −1.6 in B) | **H3 rejected.** Round-priced resting orders aren't stale. |
| 5 | 10-10 | `research/window_profile.py`: per-second variance across the window (ETH 28k, SOL 12k windows) | research | Strong decay: 30 s bins 1.44 → 0.73 (ETH A), 1.56 → 0.69 (ETH B), 1.34 → 0.83 (SOL A); first 10 s 2.0× (ETH) / 1.75× (SOL); every minute starts with a burst | New structural fact; motivates H4. |
| 6 | 10-10 | **H4**: `research/profile_fav.py` (ETH): log(iv/rv_fut) by h; favourite PnL at next fill after fee by h × band (50–97¢) | research | rv_fut/rv_15m falls with h as the profile predicts (−0.04 at h 840 → −0.25 at h 180) and iv sits 0.15–0.3 log above rv_fut, but favourite PnL is −4..+2¢ with no cell positive in both halves except 80–97¢ around +0.3..+1¢ (below what survives a spread) | **H4 rejected.** The market (or costs) already absorbs the decay. |
| 7 | 10-10 | 15-min vs hourly-ladder idea (`KXBTCD` as a feasibility check) | data check | KXBTCD has only 8 days locally (Sep 22–29, all lockbox); no KXETHD / KXSOLD | Needs a download (see below). |

## Learnings
- **No sign asymmetry in 15-minute crypto vol.** The size of the last 15/60 minutes' move predicts the rest-of-window
  vol (beyond HAR terms), its sign doesn't (ETH and SOL, both halves).
- **SOL's own spot/perp taker flow carries no tradable information** for KXSOL15M (same as ETH's flow on ETH).
- **SOL's Kalshi market lags SOL spot by less than costs**, like ETH's (H0); no staleness edge for a taker.
- **Round-priced Kalshi orders aren't stale:** taker PnL at x0/x5 prices is the same −1..−2¢ as anywhere else.
- **Vol decays across every 15-minute window** (≈1.4× the window mean in the first 30 s, ≈0.75× in the last 30 s, a
  2× burst in the first 10 s, a burst at every minute mark), on ETH and SOL, weekdays and weekends. Useful for any vol
  model working inside the window (eth-volfav-style forecasts should scale remaining variance by this profile rather
  than by h). The market already prices it to within costs: late favourites are not cheap after fee + spread.
- After this session, the backfill-testable taker space on ETH/SOL looks exhausted except for the boundary reversal
  (eth-midrev / sol-midrev) and the 9:30 bell (us-hours-vol). New edges probably need new data (below).

## Current status
- Stage: **rejected at research** (5 hypotheses, H0–H4; no pipeline runs, nothing reached the pipeline's bar of a
  plausible, not clearly negative screen). Budgets untouched (0/3 full, lockbox unused).
- What would open new ground on ETH/SOL (data requests for the user; I did not download anything):
  1. **Kalshi hourly above/below ladders KXETHD and KXSOLD** (trades + settlements, Dec 2025 on; books recorded from now).
     The 15-minute market closing at :00 settles on the same 60 s CF average as the hourly ladder for that hour, so in
     the last 15 minutes of each hour the ladder's interpolated CDF at the 15-minute strike is an independent price for
     the same bet. Relative value between two thin Kalshi books (or the ladder as a fair-value anchor for the 15-min
     market). Also longer KXBTCD history to prove the concept on BTC first (only 8 days exist, all in the lockbox).
  2. **Polymarket 15-minute crypto up/down markets** (ETH/SOL), for cross-venue mispricing; they settle on a different
     reference (Chainlink), so the basis itself would need study.
  3. **Other coins' Kalshi 15-minute series** (XRP, DOGE, ...), which would also let us-hours-vol spend its last full test.
