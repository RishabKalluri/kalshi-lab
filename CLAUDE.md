# kalshi-lab: instructions for Claude

See `SYSTEM.md` for how the system fits together and `README.md` for commands.

## Git: checkpoint automatically
- Commit and push to `origin main` (github.com/RishabKalluri/kalshi-lab, private) on your own, without
  asking, whenever a meaningful unit of work is done and verified: a feature or fix working with tests
  passing, a strategy test result recorded in its folder, a deploy, or doc updates.
  Don't commit half-finished or failing work; don't commit after every small edit.
- Messages: a short summary line plus what changed and why. Never add Claude as a co-author or credit
  (no `Co-Authored-By` lines, no "Generated with" footers).
- Never commit secrets or data: `.env`, `*.pem`, recordings, backfill, `results/`, `research/data/`
  are gitignored; check `git status` before committing.
- If a push fails (auth, network), keep the local commit and tell the user.

## How the user works
- All strategy creation, testing and running goes through chat: Claude writes the strategy, runs
  `kalshi-lab test`, follows the job to its verdict, and reports in plain language.
- Make technical/trading parameter calls yourself (sizing, risk limits, thresholds) and explain briefly.
  Anything with real money (live orders, funding) needs the user's explicit go-ahead.

## Strategy development (agents)
- New strategies are developed by the `develop-strategy` skill (`.claude/skills/develop-strategy/`), one
  forked agent per strategy, each in its own folder `strategies/<slug>/` (config.json, NOTES.md, results.json,
  strategy.py). `strategies/eth-volfav/` is the reference example; `_archive/` holds older experiments.
- The pipeline (`kalshi-lab test <slug> ...`) appends every run to a hash-chained ledger
  (`results/_ledger/<slug>.jsonl`) and copies it to the folder's results.json. Budgets and the lockbox gate read
  the ledger only. `.claude/hooks/strategy_agent_guard.py` restricts subagents (not the main session).
- **Lockbox:** data from `LOCKBOX_START` (validate.py, currently 2026-08-20) on is never used by
  smoke/quick/full; each strategy gets one lockbox run after a promising full test. Move the date forward only
  deliberately and announce it.
- **Before any live trading:** run `kalshi-lab audit <slug>` (independent re-run of full + lockbox vs the
  ledger) and check the folder's results.json matches the ledger. Mismatch = stop and tell the user.

## Rules the system is built on
- Decisions come from engine results only (the validation pipeline); `research/` scripts are for screening.
- Pipeline: smoke → quick (gate) → full walk-forward over development data (strategies with a `fit()`
  classmethod are refit before each month on earlier data only, budget 3) → one-shot lockbox. Paper starts
  after a lockbox pass; live needs enough paper to check execution, a clean audit, and the user's OK.
- Tests run on the laptop (the server's burstable CPU throttles); the server runs recorder, paper
  trading, downloads and the dashboard. Deploy with `deploy/push.sh kalshi` (paper traders keep running).
- The dashboard reads strategy folders (config.json, results.json, NOTES.md); keep them and `SYSTEM.md`
  current. `strategies/_archive/registry.json` holds legacy ideas/rejections.
- The project lives in `~/Downloads/kalshi` (not iCloud-synced; iCloud offloaded files in the old Desktop copy).
