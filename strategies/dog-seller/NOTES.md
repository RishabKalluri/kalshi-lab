# Underdog Seller

Markets: KXETH15M and KXSOL15M (Kalshi 15-minute up/down; settle on the 60 s CF index average vs the
60 s average before open).

## Hypothesis (written before any pipeline test)
- **Why the market should be mispriced:** every taker screen this session and before (settle-lockin,
  btc-anchor-vol, sol-flow, sol-vomma) found the same thing: the market's price is very good, and taking
  costs fee + spread (~1.5–2¢). But *buying underdogs* as a taker loses more than that: 2–4¢/contract at real
  next fills on both coins, in both halves of development data (`btc-anchor-vol/research/bias_scan.py`),
  while buying favourites loses ~0. That's the favourite-longshot bias: lottery-ticket buyers overpay for
  10–30¢ contracts. Makers pay no fee on these series, so the passive side of those trades keeps the whole
  overpayment. On every development trade (`settle-lockin/research/maker_side.py`), the passive side of
  underdog purchases (taker paid 10–30¢) earned **+1.3..+2.1¢/contract 6–15 minutes before close** on both
  coins, positive in 7/8 months (ETH) and 8/8 (SOL).
- **Who is on the other side:** retail takers buying cheap "it could still flip" contracts mid-window. They
  keep losing because the payoff is lottery-like and losses are small and frequent-looking per trade.
- **The risk:** the +1–2¢ is the average passive side; a back-of-queue maker gets a worse subset (filled when
  a trade eats the queue, i.e. on big or informed sweeps, after spot moves toward the strike). BTC's spread
  maker died exactly there (back-of-queue fills −0.6¢ vs mid). Underdog-only quoting at least keeps us on the
  side the bias favours.
- **What would prove it wrong:** engine walk-forward (resting orders join the back of the queue at the
  configured book depth, fill only on printed trades) pooled CI below 0 or <40% of months positive; or
  positive in backfill but the recorded-book lockbox (real queues) loses.

## Design (v1)
- Quote only between `max_tau` = 870 s and `min_tau` = 360 s before close (the window where the passive
  side earned the most), cancel below `min_tau`, hold to settlement.
- Only when the underdog's price (YES ask if YES < 50¢, else NO ask = 1000 − YES bid) is in [100, 300] mills.
- One post-only order per market joining the underdog's best offer (sell YES at the YES ask, or buy YES at
  the YES bid = sell NO at the NO ask). Requote when the touch moves. Size from the sizing policy
  (cost = the favourite's price, so ~6 contracts per order at 0.5%; 5% of equity per market max).
- No spot model (the market's price beats ours; see sol-vomma, btc-anchor-vol).

## Ideas and prior work used
- `strategies/_archive/maker.py` (BTC spread maker: quoting mechanics, its back-of-queue failure).
- Research in this session: `strategies/settle-lockin/` (trades dump, maker_side.py), `strategies/btc-anchor-vol/`
  (bias_scan.py).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-01 | v1 as designed | ad-hoc May 1–8 (both coins) | **−2.28¢/ct**, 26k contracts, 1,123 markets, t −1.5. ETH −3.3¢, SOL 0.0¢. Decompose: +0.80¢ edge vs mid at fill, **−2.10¢ adverse in the next 30 s**, −0.98¢ carry | Back-of-queue fills are the adversely selected ones, as BTC's maker found. First fill per market is as bad as later ones; every time-left and price bucket negative. |
| 2 | 10-01 | added optional quote protection (pull when the last 3 s of spot implies a YES move toward the underdog > `protect` mills; delta from the market's own price), sweep protect=0/5/15 | ad-hoc Jun 1–8 | −3.03 / −3.87 / −2.91¢/ct (t ≈ −2); protection cuts volume 20–45% but not the per-contract loss | Pulling on spot moves doesn't fix it: the fills that hurt aren't spot-driven pick-offs we can see coming at 1 s. Kept default off. |
| 3 | 10-01 | v1 (protect=0) | smoke | passed: +5.1¢, 45 markets (Aug 19) | mechanics ok |
| 4 | 10-01 | v1 | quick | passed: +0.71¢, CI −2.5..+3.7, 546 markets, 3/4 days (Aug 17–20 backfill) | the gate is noise-level; two ad-hoc weeks were −2.3/−3.0¢. Full test decides. |
| 5 | 10-01 | v1 (job dog-seller-1001-123136) | **full (1/3): reject** | **−0.52¢/ct, CI −1.08..+0.08**, 987k contracts, 27.6k markets, **1/8 months positive** (Jan −3.3, Feb −2.0, Mar −0.5, Apr −0.1, May −1.6, Jun −3.4, Jul −0.5, Aug +0.1); 2× latency −0.41¢; several months stopped at the −$930 loss limit | The average passive side's +1–2¢ doesn't reach a back-of-queue maker: we get filled when a sweep eats the queue, which is the informed flow. Rejected; not retried (no motivated fix: protection didn't help, and better queue position needs speed we don't have). |

## Learnings
- **The favourite-longshot bias is real on ETH/SOL (underdog takers lose 2–4¢) but a back-of-queue maker can't
  collect it.** The passive side of all trades earns +1–2¢ on underdog sales, yet our simulated fills (back of the
  queue at book depth, filled only by printed trades) lose 0.5¢: +0.8¢ edge at fill, −2.1¢ adverse in 30 s.
  Same failure as the BTC spread maker. Queue position, not the bias, decides maker PnL here.
- Spot-move quote protection (3 s lookback) cuts volume but not the per-contract loss.
- Caveat: backfill books are synthetic (fixed depth, no cancels), so the sim's queue is pessimistic. A real-book
  test would need recorded books over many weeks, which only the lockbox has now.

## Current status
- Stage: **rejected** (full walk-forward reject). One full test of 3 used; lockbox unused.
