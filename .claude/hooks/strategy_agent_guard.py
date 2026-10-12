#!/usr/bin/env python3
"""PreToolUse guard for strategy-development agents (subagents, incl. the develop-strategy skill).

Applies only when the tool call comes from a subagent (the hook input has `agent_id`); the main session,
which maintains the infrastructure, is unaffected. Blocks (exit 2, reason shown to the agent):
  - editing pipeline records (results.json, the ledger, job reports) or the code that grades strategies
  - touching infrastructure that affects recording, downloads, paper/live trading or the server
  - reading credentials or the lockbox token; using --force or lockbox overrides
  - editing strategies other agents own (_archive, _template, anything paper/live)
These are guardrails, not a sandbox: the independent audit before any live decision is the backstop.
"""

import json
import re
import sys

PROTECTED_FILES = re.compile(
    r"(strategies/[^/]+/results\.json|results/_ledger/|results/_jobs/|"
    r"src/kalshi_lab/(validate|strategy_dir|backtest|jobs|remote|paper_ctl|engine|strategy|sizing|report)\.py|"
    r"src/kalshi_lab/(recorder|live|sim|core|data)/|deploy/|\.claude/|CLAUDE\.md|"
    r"strategies/(_archive|_template|eth-volfav)/|strategies/_budgets\.json|tests/)"
)
SECRETS = re.compile(r"(lockbox\.token|kalshi\.pem|\.kalshi/|(^|/)\.env\b)")
BASH_FORBIDDEN = [
    (r"--force\b", "--force overrides the anti-overfitting budget/lockbox rules (user only)"),
    (r"KALSHI_LOCKBOX", "lockbox settings are fixed (user only)"),
    (r"lockbox\.token|_ledger", "the lockbox token and the ledger are off limits"),
    (r"kalshi-lab\s+live\b", "agents never trade real money"),
    (r"kalshi-lab\s+(validate|enqueue|worker)\b|kalshi_lab\s+validate", "run pipeline stages through `kalshi-lab test` (it queues them one at a time)"),
    (r"KALSHI_TEST_WORKERS", "test parallelism is fixed by the machine's capacity"),
    (r"kalshi-lab\s+(paper-stop|backfill|record)\b", "stopping paper traders / downloading / recording is infrastructure: ask the user"),
    (r"\b(systemctl|ssh|scp|rsync)\b", "the server and its services are off limits; use kalshi-lab commands"),
    (r"(^|[\s;&|(`])aws\s|\.aws/|boto3|s3://", "AWS and the S3 data bucket are infrastructure (`kalshi-lab test` pulls the data it needs)"),
    (r"git\s+(push\s+(-f|--force)|reset\s+--hard|rebase|filter-branch)", "history-rewriting git commands are off limits"),
    (r"kalshi\.pem|\.kalshi/|(^|\s)\.env\b", "credentials are off limits"),
]
# Bulk market-data hosts: downloading is the user's/main session's job (on the server), never an agent's.
DOWNLOAD_HOSTS = re.compile(r"(data\.binance\.vision|data-api\.binance\.vision|binance\.com/api|static\.okx\.com|"
                            r"okx\.com/cdn|okx\.com/api/v5/market/history|traderecords|api\.exchange\.coinbase\.com|"
                            r"api\.elections\.kalshi\.com/trade-api/v2/(historical|markets))")
WRITE_HINT = re.compile(r"(>|\btee\b|sed\s+-i|\bperl\s+-[pi]|write_text|\.write\(|open\([^)]*['\"][wa]|\bmv\b|\bcp\b|\brm\b|truncate|json\.dump)")


def deny(reason: str):
    print(f"Blocked by the strategy-agent guard: {reason}. If you genuinely need this, stop and report it to the user.",
          file=sys.stderr)
    sys.exit(2)


def main():
    try:
        ev = json.load(sys.stdin)
    except Exception:
        return
    if not ev.get("agent_id"):  # main session: unrestricted
        return
    tool, inp = ev.get("tool_name", ""), ev.get("tool_input", {}) or {}
    if tool in ("Edit", "Write", "MultiEdit", "NotebookEdit"):
        path = str(inp.get("file_path") or inp.get("notebook_path") or "")
        if PROTECTED_FILES.search(path) or SECRETS.search(path):
            deny(f"{path} is protected (pipeline records, grading code, shared infrastructure or another strategy)")
        body = str(inp.get("content") or inp.get("new_string") or inp.get("new_source") or "")
        body += " ".join(str(e.get("new_string", "")) for e in inp.get("edits", []) or [])
        if DOWNLOAD_HOSTS.search(body):
            deny("downloading market data is done by the user/main session on the server; report what data you need")
    elif tool == "Read":
        if SECRETS.search(str(inp.get("file_path", ""))):
            deny("credentials and the lockbox token are off limits")
    elif tool == "Bash":
        cmd = str(inp.get("command", ""))
        for pat, why in BASH_FORBIDDEN:
            if re.search(pat, cmd):
                deny(why)
        if DOWNLOAD_HOSTS.search(cmd):
            deny("downloading market data is done by the user/main session on the server; report what data you need")
        if PROTECTED_FILES.search(cmd) and WRITE_HINT.search(cmd):
            deny("that command looks like it modifies protected files (pipeline records, grading code, infrastructure)")


if __name__ == "__main__":
    main()
