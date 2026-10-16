#!/usr/bin/env python3
"""Stop hook for autonomous research agents (research server, src/kalshi_lab/agents.py): don't let them quit early.

Applies only when KALSHI_AGENT_RUN is set (an agent run's folder); the laptop and interactive sessions are unaffected.
Blocks a stop while the agent's test jobs are queued or running, before it has written done.json, or when done.json says
"exhausted" or "needs_user" with more than EXHAUSTED_AFTER minutes left (agents gave up after 7-37 min),
unless less than WRAP_UP minutes are left before its deadline.
"""

import json
import os
import sys
import time
from pathlib import Path

WRAP_UP = 15  # minutes
EXHAUSTED_AFTER = 90  # minutes left: before then, "exhausted" means pivot to a new idea, not stop
JOBS = Path(__file__).resolve().parents[2] / "results" / "_jobs"


def block(reason: str):
    print(json.dumps({"decision": "block", "reason": reason}))
    sys.exit(0)


def main():
    run = os.environ.get("KALSHI_AGENT_RUN")
    if not run:
        return
    left = (int(os.environ.get("KALSHI_AGENT_DEADLINE", "0")) - time.time()) / 60
    if left < WRAP_UP:
        return
    pending = []
    for state in ("queue", "running"):
        for f in (JOBS / state).glob("*.json"):
            try:
                if json.loads(f.read_text()).get("agent_run") == run:
                    pending.append(f.stem)
            except (OSError, ValueError):
                pass
    if pending:
        block(f"Your test job(s) {', '.join(pending)} haven't finished: `uv run kalshi-lab wait <job>` (repeat until it "
              f"prints a verdict), act on the result and continue. {left / 60:.1f} h left.")
    done = Path(run) / "done.json"
    reason = ""
    if done.exists():
        try:
            reason = json.loads(done.read_text()).get("reason", "")
        except ValueError:
            pass
    if reason == "needs_user" and left > EXHAUSTED_AFTER:  # overnight agents quit after 7-9 minutes this way
        block(f"done.json says needs_user, but you have {left / 60:.1f} h left. Keep the request in report.md's "
              "## Requests; the user reads it in the morning. Until then, work on the best idea that uses data you have: "
              "variations of strategies that passed (derived_from), untaken IDEAS.md items, or your own, and take at "
              "least one through the pipeline. Remove or update done.json when you're done.")
    if reason == "exhausted" and left > EXHAUSTED_AFTER:
        block(f"done.json says exhausted, but you have {left / 60:.1f} h left. Your brief is where you start, not where you "
              "stop: its ideas are dead, so take the next most promising idea from strategies/IDEAS.md (untaken) or your "
              "own, in any theme, and keep going. Use what you learned. Remove or update done.json when you're done.")
    if not done.exists():
        block(f"You have {left / 60:.1f} h left and no done.json: keep going. Take the next pipeline step, or if the idea "
              "is dead, record why and pivot to the next hypothesis. Keep report.md current.")


if __name__ == "__main__":
    main()
