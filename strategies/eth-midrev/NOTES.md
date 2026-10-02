# ETH Late-Confirmed Reversal (folder eth-midrev)

Markets: KXETH15M (Kalshi 15-minute ETH up/down; YES if the 60 s average of the CF ETH index before close is at
least the 60 s average before open).

Why ETH: the user asked for ETH. It is also the market with the measured inefficiencies (eth-volfav, eth-overreact);
BTC's 15-minute market is efficient and serves as a control.

## Hypothesis 1 (written before any test): the 15-minute reversal is a general spot fact, not a boundary fact
- **Starting point:** eth-overreact found that 15-minute returns measured *between window boundaries* reverse in sign
  after big moves (~56% after |z| > 1.5, every month, all coins), and that the Kalshi price at the open ignores it.
  If the reversal is a property of crypto returns at the 10–15 minute scale (liquidation / inventory overshoots
  unwinding), it should hold at *any* clock offset, not just :00/:15/:30/:45. Then mid-window, a big trailing move
  (spanning the boundary, or inside the window) predicts drift against it over the remaining minutes, and the Kalshi
  price, which prices spot vs strike as a random walk, overprices the side the move created. That is a different set
  of markets and times from eth-overreact (which only trades the first 1.5 minutes on the previous window's move).
- **Who is on the other side:** takers and quoting bots pricing the remaining move as driftless (spot distance at
  current vol), and momentum chasers buying the side the move has pushed into the money.
- **What would prove it wrong:** (1) the sign reversal at off-boundary offsets is much weaker than at boundaries (then
  it is a boundary/settlement-flow fact, see Hypothesis 2); (2) at mid-window checkpoints, fading the trailing big
  move at the next real fill, after fee, isn't positive in both halves of development data (Jan–Apr, May–Aug 19);
  (3) it is positive only where eth-volfav already trades (iv high), or opposite to eth-volfav's favourite bet.
- **Known tension:** fading a move mid-window usually means buying the underdog, and underdog takers overpay 2–4¢
  (favourite-longshot bias, dog-seller). The reversal drift has to beat that.

## Hypothesis 2 (written after the H1 screens, before screening it): after a big *in-window* move the favourite is cheap
- **What prompted it:** in the H1 screen, fading a trailing move that happened mostly *inside* the current window lost
  −8..−12¢/contract in both halves (|z| > 1.5–2), far more than the ~3.5¢ cost of being on the wrong side of spread +
  fees. So the *follow* side (the favourite the move created) might be +4..+7¢.
- **Why mispriced:** after a sharp move inside the window, spot sits far from the strike. Retail takers buy the cheap
  underdog betting on a bounce ("it's overextended"; the reversal folklore), and makers quote the favourite as if part
  of the move will give back. Spot, though, barely reverses *within* the window (sign flip ~53% at mid-window offsets
  vs ~57% at boundaries; H1 screen), so the bounce is overpriced.
- **Who loses:** underdog buyers after big moves (the favourite-longshot bias, concentrated after moves).
- **Wrong if:** following after |z_in| > thr at the next real fill, after fee, isn't positive in both halves; or it's no
  better than buying the favourite at the same price without a big move (then it's the plain price-level bias, which
  settle-lockin found isn't there); or it mostly overlaps eth-volfav's triggers.

## Hypothesis 3 (written before screening it): BTC leads ETH spot by seconds to a minute
- **Why mispriced:** BTC is the price-discovery market; if ETH spot catches up to BTC moves with a lag of 10–60 s, the
  ETH Kalshi market (which follows ETH spot with a further small lag, eth-overreact H1) is stale twice over.
- **Who loses:** quotes on the ETH 15-minute market that update on ETH spot only.
- **Wrong if:** BTC's last 10–120 s return doesn't predict ETH's next 10–120 s return beyond ETH's own past return
  (Binance 1 s, partial corr ≈ 0), or the predicted move is far below a cent of Kalshi price.

## Hypothesis 4 (written before screening it): ETH's idiosyncratic move (vs BTC) reverses; the common move doesn't
- **Why mispriced:** much of an ETH move is just the crypto market (BTC beta); the rest is ETH-specific flow (a large
  ETH order, ETH perp liquidations). Relative-value desks trade ETH/BTC back to its level, so the ETH-specific part
  should mean-revert over minutes, while the common part doesn't (or reverses less). The Kalshi ETH price prices
  spot vs strike as a random walk and ignores which kind of move put spot there.
- **Who loses:** takers and quoters pricing ETH's distance to the strike without asking whether BTC moved too.
- **Wrong if:** in Binance 1 s, the idiosyncratic part e = r_eth − β·r_btc over the trailing 5–15 minutes doesn't
  predict the next 5–15 minutes of ETH (negative coefficient, both halves) any better than the raw ETH return; or
  fading it at mid-window checkpoints at real Kalshi fills, after fee, isn't positive in both halves.

## Hypothesis 5 (written before screening it): the 08:00 UTC Deribit options expiry moves ETH vol on a UTC clock
- **Why mispriced:** Deribit (where most ETH options trade) expires daily, weekly (Fridays) and monthly (last Friday)
  options at 08:00 UTC. Dealer gamma hedging around expiry should damp vol just before (pinning, if dealers are long
  gamma) and release it just after, as hedges come off. us-hours-vol showed vol runs on the New York clock and only
  checked NY slots, where an 08:00 UTC effect would be split across 03:00/04:00 ET by daylight saving and diluted.
  A Kalshi trader pricing off recent vol would overprice vol in the pinned window (favourite cheap) and underprice it
  in the window after expiry (underdog cheap), most of all on Fridays.
- **Who loses:** quoters and takers using trailing vol with no expiry calendar.
- **Wrong if:** no UTC-anchored (same in winter and summer) vol dip/bump around 07:45–08:15 UTC; or Fridays look like
  other days; or log(iv/rv_fut) in those windows is normal and the favourite/underdog isn't positive at next fills in
  both halves.

## Hypothesis 6 (written after the boundary-shape screen, before screening it): the *last minutes* of a window carry the reversal
- **What prompted it:** `offset_rev.py` shows the 15-minute sign reversal is U-shaped in the clock: strongest for
  intervals ending within ~2–4 minutes of a boundary (ETH flip 0.565–0.575), weakest mid-window (0.53). And in
  `boundary_shape.py` a 5-minute move ending at the boundary flips over the next 5 minutes 57%/59% (A/B) on ETH,
  holding up in May–Aug, where eth-overreact's full-window signal decayed (~+0.8¢).
- **Why mispriced:** the overshoot that reverts is a late-window burst into the boundary (15-minute candle-close
  traders, hedgers of 15-minute binaries on Kalshi/Polymarket/perps rebalancing into expiry, then unwinding after).
  The next window's strike already contains that burst, and the opening price (~50¢) ignores that it tends to give back.
- **Who loses:** the same opening takers/quoters as eth-overreact, but on a signal they also miss when the full-window
  move is unremarkable (a quiet window with a late spike).
- **Wrong if:** at the first 1.5 minutes of the next window, fading z5 = (A(open) − A(open − 300 s)) / (rv_60m·√300)
  at the next real fill, after fee, isn't positive in both halves, or isn't better in May–Aug than eth-overreact's
  z15 rule on the same rows, or adds nothing once z15 is accounted for (rows with |z5| big but |z15| small).

## Ideas and prior work used
- `strategies/eth-overreact/` (panel builder, spot caches, the boundary reversal and the |z| > 1.5 threshold).
- dog-seller (underdogs overpriced), eth-volfav (favourite cheap when iv ≫ forecast), settle-lockin (late window priced well).

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-02 | `research/offset_rev.py` (**H1**): Binance sign reversal of consecutive 15-min returns at every clock offset | research | U-shaped in the clock. ETH P(flip \| big move) 0.57/0.55 (A/B) for intervals ending at a boundary (o = 0–60 s), 0.57/0.56 at o = 660–840, but 0.53–0.54/0.51–0.52 mid-window (o = 180–360). BTC and SOL the same shape | The reversal is a boundary fact, not a general 15-minute fact. |
| 2 | 10-02 | `research/mid_fade.py` (**H1**): fade the trailing 15-min move at mid-window checkpoints, next real fill, fee | research | \|z15\| > 1.5: h 300–780 −2.2..+1.1¢ (A), −0.7..+0.8¢ (B); first trigger at h ≤ 780 +0.2/−1.3¢ (se 0.8). Only h ≥ 780 (eth-overreact's zone) is positive. Fading a move that happened *inside* the window loses −8..−12¢ | **H1 rejected.** Nothing to fade mid-window. |
| 3 | 10-02 | `research/fav_after_move.py` (**H2**): buy the favourite after a big in-window move (z_el = in-window move / rv_60m·√elapsed), by price × \|z_el\| × h | research | Mostly −1.5..+1¢ in every cell with n > 200; first trigger \|z_el\| > 2: +1.5/+0.3¢ (se 0.7–0.8) | **H2 rejected.** The −10¢ fade result was the cost of buying underdogs (spread + fees + longshot bias), not a cheap favourite. |
| 4 | 10-02 | `research/boundary_shape.py`: short-horizon (1/3/5 min) reversal around boundaries | research | 1–3 min: no clear boundary transient. 5 min ending at the boundary: ETH flip 0.57/0.59, BTC 0.55/0.56 (vs ~0.53–0.55 elsewhere) | The burst *into* the boundary is what reverses. → H6. |
| 5 | 10-02 | `research/btc_eth.py` (**H3**, **H4**): BTC lead on ETH; ETH idiosyncratic (vs β·BTC) reversal | research | H3: BTC past 10–60 s → ETH next 10–60 s coef +0.03..+0.05 in A, ≈0 or negative at 60 s in B; a 1-σ BTC move predicts ≪ 1¢ of Kalshi price. H4: idio part reverts at 5 min in A (t −11.7, overlapping) but not in B (−2.7 → ~−1 after overlap), and *continues* at 15 min in B (+0.05, t +10) | **H3 rejected** (below costs). **H4 rejected** (sign flips between halves). |
| 6 | 10-02 | `research/expiry_0800.py` (**H5**): 08:00 UTC Deribit expiry, UTC slots 06:00–09:45, Fri vs Mon–Thu, EST vs EDT | research | No UTC-anchored vol dip/bump: 07:45 −0.2, 08:00 −0.01..−0.32, 08:15 ≈ 0, on Fridays as on other days. 08:00 log(iv/rv_fut) 0.10–0.12 vs 0.22 overall, but underdog PnL Mon–Thu +2.6/+5.0, Fri −2.2/−6.0 (~30–100 markets/cell, se ~5) | **H5 rejected.** No expiry fingerprint in 15-min ETH vol. |
| 7 | 10-02 | `research/late_move.py` (**H6**): first 1.5 min, first trigger per market, fade at next fill after fee; z by late window L = 180/300/450 s | research | \|z5\| > 1.5 alone: +1.8/+2.6¢ (se 1.5/1.4). eth-overreact's \|z15\| > 1.5: +4.0/+1.7¢. **\|z15\| > 1.5 & \|z5\| > 1.5 same sign: +6.3/+5.1¢ (se 2.4/2.2, 408/499 markets)**; the rest of eth-overreact's triggers: +2.9/**+0.1**¢. Neighbours (L 300–450, thr 1.0–2.0) all +2.8..+8.5 in both halves. SOL: late-confirmed +7.7/+9.7¢, rest +8.0/+1.2¢ | The part of the reversal that survived into May–Aug is the late-confirmed move, on both ETH and SOL. Rule fixed at the pre-stated L = 300 s, thr 1.5. |
| 8 | 10-02 | v1 `LateConfirmed` ad-hoc Jun 1–15 | ad-hoc | −1.8¢/ct, 51 markets (research rule: 61 markets, +4.3¢; 50 in common) | Engine picks the research's markets; two weeks is noise. |
| 9 | 10-02 | v1 | smoke | passed (1 market) | mechanics ok |
| 10 | 10-02 | v1 (job eth-midrev-1001-233638) | quick | passed: +1.87¢, CI −27..+28, 17 markets | noise-level, go to full |
| 11 | 10-02 | v1 (job eth-midrev-1001-233732) | **full (1/3): promising** | **+5.42¢/ct, CI +2.04..+8.95**, 16.1k contracts, 814 markets, **7/9 months positive** (Dec +48 n3, Jan +4.6, Feb +5.3, Mar −4.4, Apr +18.0, May −2.0, Jun +3.5, Jul +4.9, Aug +11.1); 2× latency Jun–Aug +6.57¢ (CI +0.8..+12.7); max drawdown $166 | Matches the research (+5–6¢), and May–Aug holds at +4.4¢ where eth-overreact's walk-forward was ~+0.8¢. Go to the lockbox. |
| 12 | 10-02 | v1 (job eth-midrev-1001-234758) | **lockbox: pass** | **+6.89¢/ct, CI −1.47..+14.82**, 2.8k contracts, 135 markets, 21/40 days; Aug 20–31 −5.8¢ (40 mkts), **Sep +11.8¢** (95, CI +1.5..+20.8), recorded books Sep 29–Oct 2 −33.6¢ (5 mkts) | Pass, not strong pass (CI crosses 0 on 135 markets). The recorded-book part is 5 markets: noise. |
| 13 | 10-02 | `paper-start` (rv_scale=1.09, slip_c=1, 0.5%/order, same as eth-overreact) | paper | started on the server as kalshi-paper@eth-midrev | |

## Learnings
- **The 15-minute reversal is a boundary effect.** Consecutive 15-minute returns reverse most when the intervals end
  near :00/:15/:30/:45 (ETH flip ~57%) and least mid-window (~53%), on BTC, ETH and SOL. Fading big moves mid-window,
  following the favourite after big in-window moves, BTC→ETH lead-lag, ETH-vs-BTC idiosyncratic reversal and the
  08:00 UTC Deribit expiry all came out at or below costs (H1–H5).
- **What reverses is the burst into the boundary.** eth-overreact's trigger (|z15| > 1.5) splits cleanly: when the last
  5 minutes also moved hard the same way (|z5| > 1.5) the fade made +6.3/+5.1¢ (Jan–Apr / May–Aug); otherwise
  +2.9/+0.1¢. Same split on SOL. So eth-overreact's decay since May is the unconfirmed half; the late-confirmed half
  hasn't decayed (walk-forward May–Aug +4.4¢, lockbox Sep +11.8¢).
- Engine matched the research (+5.4¢ vs +5–6¢), as with eth-overreact: fixed opening checkpoints + next real fills
  are a reliable screen for this kind of rule.

## Current status
- Stage: **paper trading** (since Oct 2; 0.5%/order, slip_c=1, rv_scale=1.09). Full 1/3 used (promising); lockbox spent (pass).
- Overlap: every trade is also an eth-overreact trigger (same market, same side). It's a sharper version of that rule,
  not an extra edge: for live, run one or the other (this one if paper agrees), not both.
- Next: 1–2 weeks of paper (~3–4 trades/day) to check fills, then `kalshi-lab audit eth-midrev` and the user's OK.
