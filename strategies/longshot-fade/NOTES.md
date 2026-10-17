# Longshot fade (NBA/NHL game winners)

## Hypothesis (before testing)
Brief lead (research/sports_breaks.py): takers buying a side under 20c in games lose 5-7c/contract. If retail overpays for
comeback tickets, buying the favourite (NO on the longshot) at fixed in-game checks should earn money. Proven wrong if the
net edge (1c slippage + fee, clustered by game) has CI <= 0 on the full development history.

## Research (strategies/longshot-fade/research/: schedule.py, screen.py, screen2.py, scores.py, score_model.py)
Game start/end from ESPN play wallclocks (cache rebuilt in research/data/espn since /srv/kalshi-data/espn was unreadable):
2,781 of 2,788 dev events (Oct 2025 - Aug 19 2026; 2,772 with checks). Checks every 60 s from start+1 min to game end,
last YES trade within 5 min = price (804k checks). Net = outcome - (price+1c) - 0.07p(1-p), CI bootstrap over games.

1. **Longshot fade** (buy NO when YES < thr). Gross edge vs last price: NBA 2-10c +2.0c, 10-20c -0.8c, 20-30c +0.6c;
   NHL +0.65 / -0.1 / -0.9c. Net: NBA <10c +0.8c (CI -0.3..+1.7); all other buckets -1.6..-3.2c, several CIs < 0.
   By game phase: no consistent pattern (early-game worse). Mid prices are calibrated, so no directional bias.
2. **Jump continuation / reversal** (price moved >= 5/10/15c in 3 min, price 10-90c): both directions lose 1.5-3.4c net in
   both sports, CIs < 0. Trading either way only pays the spread.
3. **Pre-game calibration** (price at tip-off vs result): NBA gaps -2.5..0c, NHL 60-80c fav -2.8c (578 markets) - noise level.
4. **Score model vs market** (ESPN score + time left, logistic on logit(price) + lead/sqrt(time left), fit on first 60% of
   checks, test on last 40%): test log-loss market 0.4645 vs model 0.4684 (NBA), 0.5548 vs 0.5598 (NHL); trading gaps of
   3-8c net -1..-5c per contract, CIs straddle 0 or below. No information in the score beyond the price (and the
   in-sample coef on z is due to stale last-trade prices).

## Learnings
- The lead's "takers lose 5-7c under 20c" is what takers pay in spread + fees (~2-3c at these prices) plus noise; it is not a
  calibration bias of the price. The other side of those trades is the maker, who can't be copied by a back-of-queue sim
  (see dog-seller).
- NBA/NHL game markets are well calibrated at every phase and don't lag ESPN scores noticeably.
- Lockbox caveat: the lockbox window (Aug 20 on) is off-season; NBA/NHL games there are only a few preseason games, so
  an NBA/NHL strategy could hardly be locked even if promising.

## Iteration log
No pipeline runs (no screen was net positive; no full test budget used).

## Current status
rejected at research.
