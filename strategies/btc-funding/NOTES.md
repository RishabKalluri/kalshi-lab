# BTC Funding-Time Drift

Markets: KXBTC15M (Kalshi 15-minute BTC up/down; YES if the 60 s average of the CF BTC index before close is at
least the 60 s average before open).

Why BTC: BTC's 15-minute market is efficient on everything priced from spot alone (vol, fair value, favourites). A
mispricing there has to come from information the market doesn't look at. Perpetual-swap funding is the biggest
scheduled flow in crypto that has nothing to do with spot charts, and BTC has the deepest perp market.

## Hypothesis 1 (written before any test): positions flow around the 8-hourly funding settlement
- **Mechanism:** OKX and Binance BTC perpetuals settle funding every 8 hours at 00:00, 08:00 and 16:00 UTC. Whoever
  holds a position at that instant pays or receives funding; the sign follows the perp premium over spot (perp above
  spot → longs pay shorts). Holders on the paying side close just before the snapshot and reopen after it; basis
  traders adjust their spot hedge. If that flow is big enough, BTC spot drifts in the direction that *closes* the
  paying side before the settlement (premium > 0 → sell-off into the snapshot) and back after it.
- **Why the Kalshi market misprices it:** the windows ending at 00/08/16 UTC and the windows starting there are
  ordinary 15-minute markets. Quoters price them from spot vs strike and recent vol, with no notion of the perp
  premium, so a predictable drift of even a few basis points shows up as a few cents of mispricing at the open.
- **Who loses:** opening takers and quoters treating the funding windows like any other window.
- **What would prove it wrong:** (1) in Binance 1 s spot, the return over the window before (and after) each funding
  time, signed by the trailing perp premium (OKX perp vs Binance spot), isn't significantly different from zero in
  both halves of development data (Dec–Apr, May–Aug 19); (2) the same signed drift appears at non-funding hours
  (04/12/20 UTC), which would mean it's a general premium effect, not funding; (3) the drift is under ~0.1σ of the
  15-minute move, which is below a taker's fee plus spread; (4) fading/following it at the next real Kalshi fill
  after fee isn't positive in both halves.

## Ideas and prior work used
- `strategies/IDEAS.md` "Funding / open interest swings" (listed as a regime filter, never tested).
- `strategies/eth-midrev/` H5 (08:00 UTC Deribit expiry: no fingerprint in ETH vol; a different mechanism, same slot).
- `strategies/us-hours-vol/` (crypto vol follows the NY clock; UTC slots looked ordinary).
- Order flow history: `kalshi_lab.data.flow` (OKX perp and Binance spot, per second, Dec 2025 on).

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-07 | `research/funding_drift.py` (**H1**): Binance 1 s spot, every full hour Dec 1 – Aug 19; z of the 15 min before/after the hour (rv_60m units) signed by the OKX-perp-vs-Binance-spot premium over [H−60m, H−15m), raw and demeaned (trailing 7-day median); funding hours 00/08/16 vs the other 21 | research | Premium is −4.7 bp ± 0.75 bp *always* (venue gap, not funding sign), so the raw sign is constant. Demeaned-signed z: funding hours pre −0.02/−0.14, post +0.01/+0.07 (A/B, se 0.06–0.09); other hours within ±0.03. Per funding hour the signs flip between halves (e.g. 08:00 pre −0.14 A, +0.11 B). Vol (mean z²) at 08/16 is ordinary; 00 UTC is noisy (outliers) | **H1 rejected.** No funding-time drift or vol bump in BTC spot that survives both halves; nothing to sell to the Kalshi market. |

## Learnings
- OKX perp vs Binance spot is a stable ~−4.7 bp venue gap (sd 0.75 bp); it is not a usable proxy for the funding sign.
  A real funding-rate test would need OKX's funding-rate history (public API), which isn't downloaded; but with no
  unconditional drift or vol bump at 00/08/16 UTC either, a signed effect would have to be large and hidden, which is
  unlikely to justify the data request.
- BTC spot shows no fingerprint of the 8-hourly funding settlement in 15-minute returns or vol (Dec–Aug).

## Current status
- Stage: **rejected at research** (H1). Folder kept as the record; no pipeline runs.
