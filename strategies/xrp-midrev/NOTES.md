# XRP Late-Confirmed Reversal (folder xrp-midrev)

Market: KXXRP15M. Port of eth-midrev's `LateConfirmed` rule to XRP, unchanged (see strategies/eth-midrev/NOTES.md, sol-midrev).

## Hypothesis 1 (written before any test)
The reversal of bursts that run into a 15-minute boundary is a general crypto/Kalshi fact (holds on BTC/ETH/SOL spot per
eth-overreact). Rule is fixed: |z15|>1.5 (strike to strike, rv_60m units), |z5|>1.5 over the last 300 s before the open,
same sign; buy the reversal side at the touch at the first of h=870/840/810/780 s, mid 30-70c; hold. No tuning on XRP.
Wrong if: full not promising, or lockbox loses. Known risk: thin books (book_depth from config), wider spreads on XRP.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-14 | v1 unchanged port | full 1/3 | inconclusive: +3.44c, CI -0.93..+7.48, 523 mkts, 4/7 months positive (Feb +4.1, Mar +7.0, Apr +4.4, May -4.4, Jun -1.5, Jul +0.7, Aug +14.8); 2x latency +5.0c CI -1.7..11.2 | Edge on XRP smaller and not proven; no lockbox. |

## Learnings
- Smoke has no fills (rare trigger); ad-hoc dev-date backtest used for mechanics.
- The ETH-set rule does not transfer cleanly to the thin new coins: XRP weak/inconclusive, DOGE walk-forward lumpy then failed the lockbox. Together with SOL's weak lockbox (+2.1c) the ETH result looks like the best case.

## Current status
parked. Inconclusive full (1/3 used); unchanged rule, no retune. Not worth lockbox.

## Research screens run from this folder (all on XRP/DOGE development data, no pipeline runs)
open_screen.py (spot-vs-strike fair vs fills at the open): no edge. open_calib.py (calibration by price bucket): fills lose fee+spread. prev_outcome.py (anchoring on previous outcome): y-mid 1-3c < costs. round_strike.py: signs flip between halves. marketwide.py (does the plain z15 fade work better when other coins moved too): nearly all triggers are market-wide; the plain fade decays XRP +6.1 -> -0.9c, DOGE +7.5 -> -2.6c (Jan-Apr -> May-Aug). react_screen.py (Kalshi lag vs own spot, lag 30 s): every decile <= +0.3c after costs. BTC lead on XRP/DOGE spot (inline): 99th-pct BTC 10 s move predicts <=1.1bp, <= ~2c of Kalshi price.
