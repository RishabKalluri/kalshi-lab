# CME Sunday Reopen Bell (cme-reopen)

## Hypothesis (written before any screen)
- CME bitcoin/ether futures trade Sunday 18:00 ET to Friday 17:00 ET with a daily 17:00-18:00 ET break. The Sunday
  18:00 ET reopen ends ~49 hours without the main institutional venue; weekend spot vol is 0.6-0.9x weekday
  (us-hours-vol). If the reopen is a vol step, Kalshi (pricing off calm trailing weekend vol) underprices the move in
  the 18:00 ET window, as us-hours-vol found for the 9:30 ET bell, so the underdog is cheap there.
- Who loses: favourite buyers / quoting bots using trailing vol without a weekly clock prior.
- Placebos: the same 18:00 ET slot on other weekdays (daily reopen, smaller), Saturday 18:00, and neighbouring slots.
- Wrong if: no vol step in the Sunday 18:00 window, or the underdog at the next real fill after fee isn't positive
  in both halves (A < May, B May-Aug 19).
- Prior work: us-hours-vol (9:30 bell, research/open_dog.py), bell-vol (Asian/London opens: no step).

## Iteration log
| # | date | change | stage | result | learning |
|---|------|--------|-------|--------|----------|
| 1 | 10-13 | `research/reopen.py` on ETH | research | Sun 18:00 vol **+0.87** log vs month mean (Sun 17:45 +0.18, Sat 18:00 −0.26, Mon/Wed 18:00 +0.19/+0.35); gap log(iv/rv_fut) **0.00** vs 0.23 all windows; underdog **+17.6¢ (A, n=10) / +14.0¢ (B, n=10)**, se ~16¢ | Mechanism there on ETH (a vol step that's underpriced), sample tiny |
| 2 | 10-13 | same on SOL (series fixed in advance as ETH+BTC+SOL, before seeing SOL) | research | vol step +0.63, but gap −0.10 ≈ normal (−0.12); underdog −11.6 / −3.7¢ | SOL prices the reopen, like it priced the 9:30 bell (us-hours-vol: SOL −0.5¢). Expect SOL to dilute |
| 3 | 10-13 | v1 ReopenUnderdog (us-hours-vol's OpenUnderdog, clock = Sunday 18:00 ET, all params unchanged), ad-hoc ETH, six Sundays Jun 7–Jul 12 | ad-hoc | 3 trades (+30.6, +11.0, −10.4 $), 3 Sundays no qualifying underdog | mechanics as intended |
| 4 | 10-13 | v1 smoke, slots widened to Wed 14:00–20:45 ET (smoke window has no Sunday) | smoke | passed | mechanics only |
| 5 | 10-13 | v1 (job cme-reopen-1013-020555) | quick | "rejected": **0 trades**, the quick window (Aug 17–19, Mon–Wed) has no Sunday | artifact of the window, not a result |
| 6 | 10-13 | `research/reopen.py` on BTC | research | vol step **+0.91**, gap 0.05 vs 0.28 overall (vol underpriced ~0.23 log, as on ETH), but underdog only +1.1 / −6.5¢ (n=10/11) | The vol gap is there on BTC and ETH; underdog PnL follows only on ETH. Three-coin research mean ≈ +1.8¢ (se ~6): the pipeline is unlikely to find a CI > 0 |
| 7 | 10-13 | v1 (job cme-reopen-1013-020724) | **full (1/3): queued/running at session end** | partial: Jan −$31.3 on 3 markets; the verdict will land in results.json | the next session should read it before doing anything else |

## Learnings
- **The CME Sunday 18:00 ET reopen is a weekly vol bell** on every coin: window vol +0.87 (ETH), +0.91 (BTC), +0.63 (SOL)
  log above the month mean, about as big as the 9:30 ET bell (+1.03). Saturday 18:00 shows nothing, and the daily
  18:00 reopen on Mon–Wed only a small step (+0.1..+0.35).
- On ETH and BTC Kalshi underprices it (gap log(iv/rv_fut) ~0.0 vs ~0.25 normally), but the underdog only pays on ETH
  (+16¢ both halves, n=20); BTC ≈ −3¢, SOL ≈ −8¢. That's the same coin pattern as the 9:30 bell (ETH > BTC > SOL).
- With roughly one market per coin per week (~100 markets over 8 months on three coins), a real +4¢ edge would still show
  a CI of about ±8¢. Like us-hours-vol, this is limited by the sample, not by the rule.
- The quick stage always has 0 trades for a once-a-week rule (its window is the last 3 dev days, Mon–Wed), so it reports
  "rejected at quick" with no trades. That's an artifact; queue the full stage directly.

## Current status
- Stage: **full test 1/3 queued** (job cme-reopen-1013-020724, v1, rule unchanged from us-hours-vol), verdict pending.
- Next: read the verdict. If it's promising, run the lockbox (family us-hours-vol, which hasn't used it on any market). If
  it's inconclusive, consider pooling with us-hours-vol: both are "scheduled vol bell underdog" rules, and a combined
  9:30-weekday + Sunday-18:00 rule doubles the sample, but it would be a new pre-registered version inside us-hours-vol's
  family. Don't tune the clock or price band on this data.
