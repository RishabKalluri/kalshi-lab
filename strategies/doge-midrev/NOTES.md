# DOGE Late-Confirmed Reversal (folder doge-midrev)

Market: KXDOGE15M. Port of eth-midrev's `LateConfirmed` rule to DOGE, unchanged (see strategies/eth-midrev/NOTES.md, sol-midrev).

## Hypothesis 1 (written before any test)
The reversal of bursts that run into a 15-minute boundary is a general crypto/Kalshi fact (holds on BTC/ETH/SOL spot per
eth-overreact). Rule is fixed: |z15|>1.5 (strike to strike, rv_60m units), |z5|>1.5 over the last 300 s before the open,
same sign; buy the reversal side at the touch at the first of h=870/840/810/780 s, mid 30-70c; hold. No tuning on DOGE.
Wrong if: full not promising, or lockbox loses. Known risk: thin books (book_depth from config), wider spreads on DOGE.

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-14 | v1 unchanged port | full 1/3 promising +6.39c CI +1.10..+11.88, 309 mkts, 4/6 months >0 (Mar +11.2, Apr -0.3, May +0.3, Jun +9.7, Jul +13.9, Aug +1.4), 2x lat +9.4c | | 
| 2 | 10-14 | v1 | lockbox | **fail: -4.68c, CI -15.8..+6.4**, 84 mkts, 16/39 days | Walk-forward gain driven by Jun-Jul; edge not confirmed. Rejected. |

## Learnings
- Smoke has no fills (rare trigger); ad-hoc dev-date backtest used for mechanics.
- The ETH-set rule does not transfer cleanly to the thin new coins: XRP weak/inconclusive, DOGE walk-forward lumpy then failed the lockbox. Together with SOL's weak lockbox (+2.1c) the ETH result looks like the best case.

## Current status
rejected. Lockbox failed (-4.7c). Rejected; do not rerun.
