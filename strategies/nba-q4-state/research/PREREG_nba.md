# NBA Q4 taker rule: pre-registration (written 2026-10-22 before any Kalshi quote dated >= 2026-01-01 was scored)
Models: work/model1.joblib = HistGradientBoosting on PBP snapshots, trained on ESPN seasons 2017-2024 only (2024-25 = "2025" used
for PBP-only checks; Kalshi history does not cover it). Frozen; no refit.
Rule R: snapshots at game-seconds-remaining T in {300,180,120,60} of Q4 (first play with clock <= T; state after that play).
Quote: home-team KXNBAGAME market; buy YES at the next yes-taker print within 60 s after (play wallclock + 10 s) if p_hgb - ask - fee >= 2c,
else buy NO at 1 - (next no-taker print) if (1-p_hgb) - (1-bid) - fee >= 2c; fee = 0.07 p (1-p) per contract; flat 1 contract.
Why Q4-only: on the dev window (Oct-Dec 2025, 494 games) the rule at T=300..60 realized +4..+10c (CI partly > 0) while T=720/480 did not,
i.e. the choice is dev-motivated and multiple-testing-affected; reported as such.
Primary test: Jan 1 - Jun 2026 Kalshi games (808 games). Metric: realized c/contract with game-clustered bootstrap 95% CI.
Reading: "edge" only if CI > 0; secondary: all six T, fill<=20 s, and blend rule B (frozen weights from blend.joblib). Checked once.

## Addendum (2026-10-22, written after the first test, labelled SECOND LOOK at the same Jan-Jun data)
A possession-level Monte Carlo (mcsim.py; empirical possession duration/points by time-left x offense-lead bucket from 2017-2024 Q4 possessions,
home/away shift from the pregame spread, OT as spread-tilted coin; 3000 sims) was built after the test. On 2024-25 PBP-only log loss it beats HGB and
logistic at every T, and on the dev window it carries more information beyond the Kalshi mid than HGB does. Rule C (frozen from dev only, T in 300/180/120/60,
edge >= 2c): p* = sigmoid(a*logit(mid) + b*logit(mc) + c) with (a,b,c) fit on Oct-Dec 2025. Its Jan-Jun 2026 result is a second look at data already used; treat
any positive number as weaker evidence than rule R's (which was one look).
