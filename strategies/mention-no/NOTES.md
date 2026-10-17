# Mention NO (mention-no)

Agent run 20261017-0100-1. Brief: most promising untaken idea. Found by screening every backfilled series that no one had
screened (KXTRUMPMENTION, KXMLBHR/TOTAL, KXNBATOTAL, tennis, UFC, WTI, EURUSD, indices, RT, gas, LOWTNYC, KXBTCD/ETHD)
with `strategies/nhl-quiet/research/screen.py` + `side_price.py`. **All of these are 150-market samples** in
`/srv/kalshi-data/backfill/kalshi/` (KXTRUMPMENTION 86 events), so nothing there can be proven with the pipeline.

## Hypothesis (written before any pipeline run; there is none)
"What will Donald Trump say during <event>?" markets: one YES/NO market per word. Retail buys the YES lottery ticket
(headline words), and the base rate that a given word is said is low (150 sampled markets: 36% YES).

## Research (dev data only; research/early_price.py)
- Taker view: YES takers at 30-70c lose 16-40c/contract, NO takers at 30-50c earn +34c (event-clustered CIs wide).
- Fixed-time view (leak-free; price of the first trade >= h hours after the market's first trade vs outcome, 10-90c):
  h=0 mean (outcome - price) -13.9c (cluster se 4.4, 77 events, halves -19.5/-8.3), h=3 -9.3c (se 4.3), h=6 -5.6c (se 4.9).
  So the mispricing is largest at listing and decays as the event approaches.
- Tradable version: SELL YES at the bid proven by a taker-sell trade, net of the 0.07p(1-p) fee: h0 +6.5c (se 3.8, 133 mkts),
  h1 +3.7c, h3 +3.0c; the 30-70c band +8.6c at h0 (both halves +8.9/+8.5). Weak (t~1.7) but consistent in sign, and in
  line with the favourite-longshot logic. Bids from trades are an approximation (no books for this series).
- Same screens found two other one-sided biases on samples, same data limit: **NBA/MLB totals: YES (over) is underpriced**
  (outcome - price +7.5c both, cluster se 4.1/3.8, 138/130 events; NBA halves +3/+12, MLB +10/+5) and **WTI above/below
  strike: YES overpriced** (-9..-13c, se ~5.5, probably a drifting-price regime: Mar-Aug oil fell, so not trusted).

## Needs from the user (blocks everything)
1. Full history download of KXTRUMPMENTION (and any sister mention series, e.g. other speakers/earnings-call mentions if
   the same "will X say Y" format exists), plus KXNBATOTAL and KXMLBTOTAL (and KXNFLTOTAL if available).
2. MARKETS entries for them in `src/kalshi_lab/recorder/config.py` (settlement like the sports/weather entries,
   needs_strike False, quadratic fee; mention markets close early when the word is said, so settle_poll_s small).
3. Ideally recorded books for the mention series (the screen's bids come from taker-sell trades).
Only then can a pipeline run (smoke -> quick -> full) say anything. The mention effect is largest right at listing, so
real books at listing matter (the first quotes may be wide or absent).

## Status
parked at research, 0 full tests used, 0 lockbox runs used.
