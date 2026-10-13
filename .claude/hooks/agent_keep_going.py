#!/usr/bin/env python3
"""Stop hook for autonomous research agents (research server, src/kalshi_lab/agents.py): don't let them quit early.

Applies only when KALSHI_AGENT_RUN is set (an agent run's folder); the laptop and interactive sessions are unaffected.
Blocks a stop while the agent's test jobs are queued or running, or before it has written done.json, unless less than
WRAP_UP minutes are left before its deadline.
"""

import json
import os
import sys
import time
from pathlib import Path

WRAP_UP = 15  # minutes
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
    if not (Path(run) / "done.json").exists():
        block(f"You have {left / 60:.1f} h left and no done.json: keep going. Take the next pipeline step, or if the idea "
              "is dead, record why and pivot to the next hypothesis. Keep report.md current.")


if __name__ == "__main__":
    main()
