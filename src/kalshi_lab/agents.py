"""Autonomous strategy agents on the research server: a daily batch of headless Claude sessions, each running the
research-strategy skill (.claude/skills/research-strategy/) on one brief until it's done or its time is up.

    kalshi-lab agents-run [--parallel N] [--hours H] [BRIEF ...]   (systemd kalshi-agents.service, user `agent`)

Briefs come from the command line, else the first lines of BRIEFS (the head agent or the user writes them), else
DEFAULT_BRIEFS. Each run gets a folder RUNS/<id>/ (brief, Claude's stream log, report.md, done.json); the
agent_keep_going Stop hook keeps it working until done.json or its deadline. A session that dies early (crash, rate
limit) is resumed with `claude --resume` until the deadline.

Safety layers: Claude Code's auto permission mode (a classifier reviews risky actions; nothing to approve, since no one
is watching), the strategy-agent guard hook, and the OS: the `agent` user can't read lockbox data or credentials,
can't write the ledger, code or paper/live strategies, and its tests run in kalshi-sandbox.
"""

import argparse
import json
import os
import re
import subprocess
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOME = Path(os.environ.get("KALSHI_AGENTS_HOME", "/srv/kalshi-agents"))
RUNS = HOME / "runs"
BRIEFS = HOME / "briefs.txt"
DEFAULT_BRIEFS = ["your choice: the most promising untaken idea in strategies/IDEAS.md, or your own",
                  "KXSOL15M: your choice of idea"]
MAX_RESUMES = 8
MODEL = "claude-sonnet-5-5"  # pinned: the account default (or a usage-limit fallback) would change it


def claude() -> str:
    return str(Path("~/.local/bin/claude").expanduser())


def take_briefs(n: int) -> list[str]:
    """Pop up to n briefs from BRIEFS; fill the rest with defaults."""
    lines = BRIEFS.read_text().splitlines() if BRIEFS.exists() else []
    briefs = [ln.strip() for ln in lines if ln.strip() and not ln.startswith("#")]
    taken = briefs[:n]
    if taken:
        BRIEFS.write_text("".join(ln + "\n" for ln in lines if ln.startswith("#") or ln.strip() not in taken))
    defaults = (DEFAULT_BRIEFS * n)[len(taken):n]
    return taken + defaults


def run_one(brief: str, rdir: Path, deadline: float):
    env = dict(os.environ, KALSHI_AGENT_RUN=str(rdir), KALSHI_AGENT_DEADLINE=str(int(deadline)))
    meta = {"brief": brief, "started": datetime.now(timezone.utc).isoformat(),
            "deadline": datetime.fromtimestamp(deadline, timezone.utc).isoformat(), "session": None, "sessions": []}
    log = open(rdir / "stream.jsonl", "a")
    for attempt in range(MAX_RESUMES + 1):
        left = deadline - time.time()
        if left < 10 * 60 or (rdir / "done.json").exists():
            break
        if meta["session"]:
            prompt = ["--resume", meta["session"], "Your session was interrupted. Continue where you left off "
                      "(check report.md, your strategy folders and `uv run kalshi-lab jobs`)."]
        else:
            prompt = [f"/research-strategy {brief}"]
        cmd = [claude(), "-p", *prompt, "--output-format", "stream-json", "--verbose", "--permission-mode", "auto",
               "--model", MODEL]
        t0 = time.time()
        proc = subprocess.Popen(cmd, cwd=ROOT, env=env, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        killer = threading.Timer(left, proc.terminate)
        killer.start()
        for line in proc.stdout:
            log.write(line)
            log.flush()
            if not meta["session"]:
                m = re.search(r'"session_id":\s*"([0-9a-f-]{36})"', line)
                if m:
                    meta["session"] = m.group(1)
                    (rdir / "meta.json").write_text(json.dumps(meta, indent=1))
        rc = proc.wait()
        killer.cancel()
        meta["sessions"].append({"attempt": attempt, "rc": rc, "minutes": round((time.time() - t0) / 60, 1)})
        (rdir / "meta.json").write_text(json.dumps(meta, indent=1))
        if time.time() - t0 < 120:  # died at once (rate limit, outage): wait before resuming
            time.sleep(min(15 * 60, max(0, deadline - time.time() - 10 * 60)))
    done = rdir / "done.json"
    meta["finished"] = datetime.now(timezone.utc).isoformat()
    meta["outcome"] = json.loads(done.read_text()).get("reason", "?") if done.exists() else "deadline"
    (rdir / "meta.json").write_text(json.dumps(meta, indent=1))


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab agents-run", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("briefs", nargs="*")
    ap.add_argument("--parallel", type=int, default=2)
    ap.add_argument("--hours", type=float, default=6)
    a = ap.parse_args(argv)
    briefs = a.briefs or take_briefs(a.parallel)
    deadline = time.time() + a.hours * 3600
    threads = []
    for i, brief in enumerate(briefs):
        rdir = RUNS / f"{datetime.now():%Y%m%d-%H%M}-{i + 1}"
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "brief.txt").write_text(brief + "\n")
        print(f"{rdir.name}: {brief}", flush=True)
        t = threading.Thread(target=run_one, args=(brief, rdir, deadline))
        t.start()
        threads.append(t)
        time.sleep(60)  # stagger: the second agent sees the first one's IDEAS.md claim
    for t in threads:
        t.join()
    print("all agents finished", flush=True)
