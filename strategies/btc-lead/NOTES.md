# BTC Lead

Markets: KXETH15M, KXSOL15M. Status: rejected at research (no pipeline run, no budget used).

## Hypothesis (written before any test)
- Mispricing: BTC leads ETH/SOL; Kalshi quotes on the thinner markets reprice after the coin's spot does.
- Other side: slow retail quotes.
- Wrong if: after a BTC move the coin's own continuation, converted to cents of Kalshi price (~1.3c per bp at the money,
  early in the window), is below fee (~1.75c at 50c) + spread + 150 ms latency.

## Prior work
eth-midrev H3 already rejected BTC->ETH spot lead at 10 s+ horizons (coef 0.03-0.05, << 1c). This run adds 1-10 s horizons and SOL.

## Research (dev data only, Binance 1 s, 2025-12 .. 2026-08-19; `research/spot_lag.py`, `research/spot_tail.py`)
- Regression of coin return [t,t+F] on own and BTC return [t-L,t]: BTC coef is highly significant but small
  (ETH +0.07..+0.16, SOL +0.17..+0.37; own coef ~0 / negative on SOL). Mean forward move after a BTC move beyond the
  99th pct (>5 bp in 3 s): ETH +0.2..+0.3 bp, SOL +0.3..+0.5 bp, i.e. <= ~0.6c of Kalshi price.
- Tail (|BTC 3 s move| >= 99.99th pct, 21 bp, ~2k events in 8 months): ETH +0.3..+0.65 bp, SOL +0.9..+2.1 bp (F=1..10 s).
  The coin has already moved ~28-32 bp in the same 3 s, so what is left is a small remainder. Best case SOL tail
  ~2 bp = ~2.6c gross, before the 1.75c fee, spread, 150 ms latency, and only ~9 events/month/market.
- Verdict: opportunities are plentiful but edge per trade is far below costs; the tail where edge approaches costs is rare
  (a few events a month). Not worth a pipeline run. BTC's Kalshi market was not tested separately: it follows BTC spot, so it
  carries no information spot does not.

## Learnings
- ETH/SOL spot reprices to BTC within the same second; a 1 s lead exists but is worth < 1 bp.
