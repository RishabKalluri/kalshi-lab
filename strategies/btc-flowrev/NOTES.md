# BTC Kalshi-Flow Reversal (folder btc-flowrev)

Markets: KXBTC15M (Kalshi 15-minute BTC up/down; YES if the 60 s average of the CF BTC index before close is at
least the 60 s average before open).

Why BTC: the user asked for a new BTC strategy. BTC's 15-minute market is the deepest and has priced every
*spot-based* signal tried so far (vol ratio, fair value, favourites, open edge, the boundary reversal since May).
What hasn't been tested on BTC is the market's own order flow: moves in the Kalshi price that spot doesn't explain.

## Hypothesis 1 (written before any test): Kalshi-only price moves revert
- **Why mispriced:** the Kalshi price moves for two reasons: spot moved (information, priced by fast quoters) or
  Kalshi takers pushed through the book without a spot move (retail chasing a recent candle, someone sizing in,
  a hedger). The second kind is price impact without information. On a binary with a fixed 15-minute life, quoters
  who get run over widen and lean, so the price overshoots and should drift back towards the spot-implied value.
- **Who loses:** impatient Kalshi takers who move the price on their own flow, and the quoters who follow them.
- **Measure (fixed in advance):** at fixed checkpoints (seconds left h = 780, 660, 540, 420, 300, 180), the Kalshi
  residual move over the last 60 s = (Kalshi VWAP in the last 10 s − VWAP 60–70 s earlier) − (change in a spot model
  price Φ(D/(σ√τ)) with D = Binance spot − strike, σ = trailing 60-min realized vol, over the same 60 s).
  Fade large residuals at the next real Kalshi fill after the checkpoint, after taker fee, hold to settlement.
- **Wrong if:** the fade of the top residual decile/quintile isn't positive at next fills after fee in both halves
  of development data (Dec–Apr, May–Aug 19), or the residual doesn't predict the settlement outcome beyond the
  current price (then the moves are informed and the right trade would be to follow, which must also be checked).

## Hypothesis 2 (written before screening it): ETF fixing-window momentum (15:00-16:00 ET)
- **Why mispriced:** US spot BTC ETFs (IBIT, FBTC, ...) strike NAV off the CME CF Bitcoin Reference Rate NY variant,
  computed from 15:00 to 16:00 ET. Authorized participants filling the day's creations/redemptions buy/sell BTC in that
  hour, and ETF flows follow the day's price action (inflows on up days). So the NY session's return so far should
  predict the direction of the four 15-minute windows from 15:00 to 16:00 ET (intraday momentum, the crypto version of
  Gao-Han-Li-Zhou's last-half-hour effect, with the ETF fixing as the mechanism). Kalshi's 15-minute price at the open
  is close to 50/50 driftless and has no reason to lean on the session's return.
- **Who loses:** opening takers and quoters treating these windows as driftless; the counterparty flow is the ETF APs,
  who must trade in that hour regardless of price.
- **Measure (fixed in advance):** predictor R = Binance BTC log return from 09:30 ET to the window's open, divided by
  trailing 60-min vol x sqrt(elapsed). Target: the window's outcome. Slots 15:00/15:15/15:30/15:45 ET on US trading
  days (Mon-Fri, non-holiday). Controls: the same predictor on other weekday slots and on weekends (no ETF fixing).
  Trade at the open (h = 870..780) with the session-return side, at the next real fill after fee.
- **Wrong if:** corr(R, window return) in the 15-16 ET slots isn't positive in both halves (Dec-Apr, May-Aug 19), or
  it's no bigger than the control slots, or following it at next fills isn't positive after fee in both halves.

## Hypothesis 3 (post-hoc, from H2's screen; written before the checks below): post-fixing reversal at 16:00 ET
- **Origin (honest):** H2's per-slot table (28 trading-day slots 10:00-16:45 ET) showed the 16:00-16:15 ET window
  reversing the session return at corr -0.36 (A, n~150) / -0.33 (B, n~75), the strongest slot in both halves. Found by
  looking, so it needs controls and the walk-forward/lockbox are the real tests.
- **Mechanism:** the session's flow (ETF creations/redemptions filled into the 15:00-16:00 ET CF fixing, equity-hedged
  books trading with the US cash session) pushes BTC in the session's direction; at 16:00 the fixing and the equity
  close end, that pressure stops, and part of the impact reverts in the next 15 minutes. Kalshi's 16:00 window opens
  near 50/50 without leaning against the session.
- **Checks (fixed now):** (a) the same 16:00 ET slot on weekends/holidays (no fixing, no cash close) should show no
  reversal; (b) fading R at the 16:00 window's open (h = 870..780, mid 30-70c) at next real fills after fee positive in
  both halves; (c) months mostly positive. If (a) shows the same reversal, it's a clock effect, not the fixing (still
  tradable but a different story).

## Ideas and prior work used
- `strategies/settle-lockin/` (Kalshi trade-size signals on ETH/SOL: copying/fading big prints loses fee + spread;
  this tests the *price residual*, not trade size, and on BTC).
- `strategies/btc-midrev/research/trades_dump_par.py` (BTC Kalshi trades with aggressor side, dev only) and
  `strategies/eth-overreact/research/panel.py` (1 s Binance spot arrays).

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-10 | `research/flow_panel.py` + `screen_h1.py` (**H1**): Kalshi 60 s residual move (Kalshi VWAP change minus spot-model change) at h = 780..60 | research | Kalshi and spot-model moves correlate 0.73; residual doesn't predict y − last price (t −0.5 / −0.6, A/B); fading loses −1.3..−2.8¢ in every |residual| quintile, both halves, every month | **H1 rejected.** BTC Kalshi-only moves are neither overshoot nor information; fading or following pays fee + spread. |
| 2 | 10-10 | `research/screen_h2.py` (**H2**): session return (09:30 ET → window open, in vol units) vs the 15:00–15:45 ET windows | research | corr −0.08 / −0.13 (A/B), the wrong sign; following it at the open loses −5.4/−4.9¢ | **H2 rejected** (no momentum into the fixing). But the per-slot table showed the **16:00 ET** window reversing the session: corr −0.36 / −0.33 → H3. |
| 3 | 10-10 | H3 checks (`screen_h2.py` tail, `h3_coins.py`) | research | BTC 16:00 trading days corr −0.36/−0.33 (n 147/76); Oct–Nov 2025 (spot before Kalshi history) −0.60/−0.45; weekends +0.06/−0.30 (n 66/35); ETH −0.34/−0.38, SOL −0.27/−0.46. Kalshi fade at next real fills, h=870: +11.4 (se 5.7, n 65) / +10.9 (se 5.9, n 65); \|R\|>0.5: +9.7/+11.9; \|R\|>1: +13.7/+24.9 | Real in spot on all three coins and both halves, and Kalshi doesn't price it. Weekends mixed, so partly a clock effect. Chose \|R\| > 0.5 (a meaningful session move; not the best-looking cut). |
| 4 | 10-10 | v1 `SessionFade`: 16:00 ET window on NYSE full trading days, \|R\|>0.5, first of h 870/840/810/780 with mid 30–70¢, touch IOC | ad-hoc Jun 1–15 | 6 trades = exactly the research rule's 6 (\|R\|>0.5) with matching R; +32¢/ct (noise) | mechanics verified |
| 5 | 10-10 | v1 | smoke | **failed: no fills** | the smoke window (Aug 19 18:00–24:00 UTC) starts after 09:30 ET, so there's no session anchor (backtests have no spot warm-up). Not a strategy bug. |
| 6 | 10-10 | v1 (job btc-flowrev-1010-173207, `--skip-smoke`) | quick | passed: −51¢/ct, 2 markets | noise-level sample (one window a day); go to full |
| 7 | 10-10 | v1 (job btc-flowrev-1010-173341) | **full (1/3): inconclusive** | **+7.27¢/ct, CI −2.5..+16.1**, 2,251 contracts, 113 markets, **5/9 months**: Dec −9.6, Jan +12.9, Feb +10.0, Mar +18.6, Apr −13.1, May −3.4, Jun +39.5, Jul +5.0, Aug −12.3; 2× latency Jun–Aug +11.8¢ (CI −5.7..+28.7) | Sample-limited (one market a day, ±50¢ outcomes: se ≈ 4.7¢). Engine by \|R\|: 0.5–1 −6.5¢ (n 37), 1–1.5 +16.1 (n 27), >1.5 +15.1 (n 49), the same ordering as research, but raising the threshold now would be selecting on the full test. Next: more markets, not tuning: the same rule unchanged on ETH+SOL+BTC in `strategies/session-fade/` (derived_from btc-flowrev). |

## Learnings
- **BTC's Kalshi-only price moves carry no signal** (H1): the 60 s Kalshi move not explained by spot neither reverts nor
  continues; fading or following pays fee + spread (≈2¢).
- **No intraday momentum into the 15:00–16:00 ET ETF fixing** (H2); the fixing-hour windows lean slightly the other way.
- **The 16:00 ET window reverses the NY session's move** (H3) on BTC, ETH and SOL spot (corr −0.3..−0.46, both halves,
  also Oct–Nov 2025), and Kalshi opens it near 50/50. Weaker but present on weekends (partly a clock effect). In the
  engine the edge comes from sessions with |R| > 1; one window a day is too few markets for a confident BTC-only test.
- Session-anchored strategies can't pass smoke (its 6 h window starts after 09:30 ET); verify ad hoc instead.

## Current status
- Stage: **parked, inconclusive** (full 1/3; lockbox not run). The rule continues unchanged on BTC+ETH+SOL in
  `strategies/session-fade/` to get enough markets; its lockbox (if it gets one) is this family's shot on KXBTC15M.
