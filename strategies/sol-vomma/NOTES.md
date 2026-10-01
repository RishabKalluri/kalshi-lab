# SOL Vomma

Markets: KXSOL15M (Kalshi 15-minute SOL up/down; YES if the 60s average of the CF SOL index before close is
at least the 60s average before open).

## The math (why "vomma")
A 15-minute up/down contract is a cash-or-nothing digital. With distance to strike D, effective time left
τ' (τ minus ~40 s, for the 60 s settlement average) and vol σ, the textbook price is P(σ) = Φ(z), z = D/(σ√τ').
Its vol sensitivities:
- vega   ∂P/∂σ   = −φ(z)·z/σ
- vomma  ∂²P/∂σ² = φ(z)·z·(2 − z²)/σ²   (sign flips at |z| = √2, a ~92% favourite)

Nobody knows σ for the next few minutes. If σ is uncertain, the fair price is the *mixture*
E_σ[Φ(D/(σ√τ'))], not Φ at a point forecast; to second order the correction is ½·vomma·Var(σ). So, for the
same expected vol, moderate favourites (|z| < √2) are worth *more* than the point-vol price and very deep
favourites (|z| > √2) worth *less*. The correction scales with vol-of-vol, which is itself forecastable
(vol clusters; vol-of-vol rises after jumps and in thin hours).

## Hypothesis (written before any test)
- **Why the market should be mispriced:** Kalshi SOL traders (thin book, ~13 contracts at best, 1/3 of ETH's
  volume) price the binary from spot distance and one sense of "how jumpy it is". They don't price the
  uncertainty of vol itself, and they overweight recent moves. A fair value built as a mixture over a calibrated
  predictive distribution of the future realized vol (HAR mean + empirical, state-dependent dispersion) should
  disagree with the market in a systematic, z-dependent way, most when vol-of-vol is high.
- **Who is on the other side:** retail takers and slow quoters using point-vol intuition: underdog lottery
  buyers, and favourite-chasers at extreme prices. ETH VolFavorite already showed ETH's market misprices vol;
  SOL is thinner.
- **What would prove it wrong:** (1) the mixture fair value is no better than the market's next real fill
  (log loss vs `next_ask`/`next_bid`); (2) trading model−market gaps at real fills after the taker fee is ≤ 0 in
  both halves of development data; (3) walk-forward months mostly negative.

## Plan
1. Research on development data (close < 2026-08-20, `research/data/KXSOL15M.parquet`): fit the HAR log-vol
   forecast and its residual distribution (vol-of-vol); check that Φ(D/(rv_fut·√τ')) is calibrated (is a vol
   mixture the right object?), then the mixture price vs real next fills.
2. Implement as a taker at fixed checkpoints (lesson from eth-volfav); `fit()` refits before each month.

## Ideas and prior work used
- `strategies/eth-volfav/` (HAR vol model, implied-vol math, fixed checkpoints, `_Hist`).
- `strategies/sol-flow/` lesson: screen against `next_ask/next_bid`, never the trade-implied mid.
- Stochastic-vol digital pricing / vanna-volga (Castagna & Mercurio 2007): vomma as the price of vol uncertainty.

## Iteration log
Newest last. Every pipeline run gets a line; every change gets a reason.

| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-01 | `research/model_vs_fill.py`: HAR log-vol forecast + vol-of-vol dispersion model (\|resid\| on log h, \|log rv5m/rv60m\|, log rv5m/rv4h); mixture fair value E_σ Φ(D/σ√τ') over the empirical standardized residuals; train Jan–Apr, test May–Aug 19 | research | log loss at checkpoints (test): next-fill mid 0.335, last-trade mid 0.343, point-vol model 0.363, **mixture 0.363**, even the ex-post-vol oracle 0.355. Trading model−fill gaps after fees: −0.8..−1.2¢ for point *and* mixture | The market beats any model built on our D (Binance spot vs the CF index, settlement averaging). Vol mixture changes log loss in the 4th decimal. |
| 2 | 10-01 | `research/market_vomma.py`: take the market's own price as the point-vol price and apply the vomma (vol-mixture) correction with our vol-of-vol forecast, so our D isn't used | research | correction is **+0.1..+0.4¢** for \|z\| < 0.8, **−0.3..−0.9¢** for \|z\| > 1.2, bigger when vol-of-vol is high, as theory says. Never exceeds ~1¢; fee + spread is ~1.5–2¢. Favourite PnL by \|z\| × vol-of-vol tercile shows no vomma pattern (deep favourites, which the correction says are overpriced, are slightly *under*priced) | **Vomma is real math but too small to trade here**: with vol-of-vol ≈ 0.25 in log terms, ½·vomma·Var(σ) is under a cent. |
| 3 | 10-01 | `research/stack.py`: logistic stack logit(mid) + model z (point or mixture) | research | in-sample +0.3..+0.5¢, out-of-sample −0.5..−1.1¢ everywhere | Nothing beyond the market price. |
| 4 | 10-01 | `research/ratio_deciles.py`: eth-volfav signal on SOL (implied/forecast vol deciles, favourite at the next real fill, after fees; thresholds from Jan–Apr) | research | monotone-ish: bottom decile −2.7/−1.1¢, top 3 deciles ≈ +1.1¢ in Jan–Apr and +0.6/+0.6/+2.5¢ in May–Aug; top 30% positive in 6/8 months. Normalizing log(ratio) by forecast vol-of-vol (a "vol z-score") changes nothing; no sign flip at \|z\| = √2 | The tradable error is vol *level*, not vol uncertainty. Build that, keep the vomma result as a documented negative. |
| 5 | 10-01 | strategy = eth-volfav method on SOL (code reused), fit pct 0.7, rv_fut filter made relative (ETH's absolute 0.05 $/√s would drop every SOL row) | ad-hoc May 1–15 | +1.94¢/ct, 4,999 contracts, 318 markets, t 0.95 | trades as intended |
| 6 | 10-01 | same | smoke | passed (9 markets, −5.2¢, noise) | mechanics ok |
| 7 | 10-01 | same | quick | passed: −0.17¢, CI −15..+13, 32 markets | uninformative, go to full |
| 8 | 10-01 | same (job sol-vomma-1001-004405) | full (1/3) | **promising: +1.93¢/ct, CI +0.57..+3.25, 37k contracts, 2,459 markets; 5/6 months positive** (Mar −4.5, Apr +4.7, May +1.6, Jun +0.7, Jul +2.9, Aug +2.6); 2× latency Jun–Aug +1.45¢ (CI −0.7..+3.6); max drawdown $232 on $1k at 0.5%/order | Same edge size as ETH (+2.16¢). Edge is in the vol level; Jan–Feb are training only. |
| 9 | 10-01 | same (job sol-vomma-1001-012318) | **lockbox: fail** | **−0.89¢/ct, CI −2.68..+0.97**, 24k contracts, 1,611 markets, 24/42 days; Aug 20–31 +1.07¢, **Sep −2.19¢ (CI −4.45..−0.02)**, drawdown $506 | Edge didn't hold out of sample. Rejected, not retried. |

## Learnings
- **Vomma on a 15-minute binary is under a cent.** The digital's vomma φ(z)·z·(2−z²)/σ² flips sign at |z| = √2
  and the mixture correction behaves exactly as theory says, but with log vol-of-vol ≈ 0.25 it moves prices
  0.1–0.9¢, less than the taker fee plus spread. A maker might use it as a quote skew; a taker can't.
- **Our spot-distance models lose to the SOL market** (log loss 0.363 vs 0.343 for the last trade), even with
  ex-post realized vol (0.355). The market's sense of where the CF index is beats Binance spot + basis.
  So screen market-relative signals (implied vs forecast vol), not "our fair value vs the price".
- SOL's rv is ~0.01 $/√s (price ~$150): any absolute-$ threshold copied from ETH code needs rescaling.

- **A promising walk-forward isn't enough.** +1.93¢ with CI above 0 and 5/6 positive months failed the lockbox,
  driven by September (−2.2¢). The vol-level edge on SOL is either
  smaller than it looked, or decaying. eth-volfav uses the same method, so its paper results deserve a close look
  for the same September weakness.

## Current status
- Stage: **rejected** (lockbox fail). One full test used of 3; lockbox spent.
- Vomma idea: documented negative (correction < 1¢, below costs for a taker). Could still serve as a small quote
  skew for a maker, but nothing here suggests a maker would beat adverse selection on SOL.
