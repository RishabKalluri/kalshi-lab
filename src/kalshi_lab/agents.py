"""Autonomous strategy agents on the research server: a daily batch of headless Claude sessions, each running the
research-strategy skill (.claude/skills/research-strategy/) on one brief until it's done or its time is up.

    kalshi-lab agents-run [--parallel N] [--droid N] [--hours H] [BRIEF ...]   (systemd kalshi-agents.service, user `agent`)

--droid N runs the last N agents on Factory's Droid (`droid exec --auto medium`: local edits, scripts and tests; no
pushes, sudo or production changes) instead of Claude Code: a second model family, on the user's Factory plan. Same
skill (read as a file), same guard and keep-going hooks (.factory/hooks.json), same OS limits (user `agent`, sandboxed
tests); the runner also re-prompts it with the keep-going hook's message whenever it stops.

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
DROID_MODEL = os.environ.get("KALSHI_DROID_MODEL", "gpt-5.3-codex")
DROID_KEY = Path("~/.factory/api_key").expanduser()  # FACTORY_API_KEY, readable only by the agent user
DROID_RESUMES = 40  # it may stop at every turn end; the keep-going hook's message restarts it


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


def keep_going(env: dict) -> str | None:
    """The agent_keep_going Stop hook's verdict: its message if the agent must continue, else None."""
    out = subprocess.run(["python3", str(ROOT / ".claude" / "hooks" / "agent_keep_going.py")], input="{}", env=env,
                         capture_output=True, text=True).stdout
    try:
        return json.loads(out)["reason"] if out.strip() else None
    except (ValueError, KeyError):
        return None


def droid_cmd(brief: str, session: str | None, nudge: str | None) -> list[str]:
    base = ["droid", "exec", "--auto", "medium", "-m", DROID_MODEL, "-o", "json", "--cwd", str(ROOT)]
    if session:
        return base + ["-s", session, nudge or "Your session was interrupted. Continue where you left off (check "
                       "report.md, your strategy folders and `uv run kalshi-lab jobs`)."]
    return base + [f"Read .claude/skills/research-strategy/SKILL.md and follow it as your instructions for this whole "
                   f"session ($ARGUMENTS there means your brief), then CLAUDE.md for the project's rules. You run under "
                   f"Factory's Droid, not Claude Code: where they name Claude Code tools, use your equivalents. "
                   f"Your brief: {brief}"]


def run_one(brief: str, rdir: Path, deadline: float, engine: str = "claude"):
    env = dict(os.environ, KALSHI_AGENT_RUN=str(rdir), KALSHI_AGENT_DEADLINE=str(int(deadline)))
    if engine == "droid":
        env["FACTORY_API_KEY"] = DROID_KEY.read_text().strip()
        env["PATH"] = f"{Path('~/.local/bin').expanduser()}:{env.get('PATH', '')}"
    meta = {"brief": brief, "engine": engine, "model": DROID_MODEL if engine == "droid" else MODEL,
            "started": datetime.now(timezone.utc).isoformat(),
            "deadline": datetime.fromtimestamp(deadline, timezone.utc).isoformat(), "session": None, "sessions": []}
    log = open(rdir / "stream.jsonl", "a")
    nudge = None
    for attempt in range((DROID_RESUMES if engine == "droid" else MAX_RESUMES) + 1):
        left = deadline - time.time()
        if engine == "droid":  # its Stop hook may not run headless: ask the hook here between turns
            nudge = keep_going(env) if attempt else None
            if left < 10 * 60 or (attempt and nudge is None):
                break
            cmd = droid_cmd(brief, meta["session"], nudge)
        elif left < 10 * 60 or (attempt and (nudge := keep_going(env)) is None):
            break  # the hook's verdict, not just done.json: a session that ends on an early needs_user is resumed
        elif meta["session"]:
            prompt = ["--resume", meta["session"], nudge or "Your session was interrupted. Continue where you left off "
                      "(check report.md, your strategy folders and `uv run kalshi-lab jobs`)."]
        else:
            prompt = [f"/research-strategy {brief}"]
        if engine != "droid":
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
                m = re.search(r'"session_id":\s*"([0-9A-Za-z_-]{8,})"', line)
                if m:
                    meta["session"] = m.group(1)
                    (rdir / "meta.json").write_text(json.dumps(meta, indent=1))
        rc = proc.wait()
        killer.cancel()
        meta["sessions"].append({"attempt": attempt, "rc": rc, "minutes": round((time.time() - t0) / 60, 1)})
        (rdir / "meta.json").write_text(json.dumps(meta, indent=1))
        if engine == "droid" and rc == 0 and nudge:
            continue  # a short turn after a nudge is normal for droid: no backoff
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
    ap.add_argument("--droid", type=int, default=0, help="run the last N agents on Factory Droid")
    ap.add_argument("--hours", type=float, default=6)
    a = ap.parse_args(argv)
    briefs = a.briefs or take_briefs(a.parallel)
    engines = ["claude"] * (len(briefs) - min(a.droid, len(briefs))) + ["droid"] * min(a.droid, len(briefs))
    deadline = time.time() + a.hours * 3600
    threads = []
    for i, brief in enumerate(briefs):
        rdir = RUNS / f"{datetime.now():%Y%m%d-%H%M}-{i + 1}"
        rdir.mkdir(parents=True, exist_ok=True)
        (rdir / "brief.txt").write_text(brief + "\n")
        print(f"{rdir.name} [{engines[i]}]: {brief}", flush=True)
        t = threading.Thread(target=run_one, args=(brief, rdir, deadline, engines[i]))
        t.start()
        threads.append(t)
        time.sleep(60)  # stagger: the second agent sees the first one's IDEAS.md claim
    for t in threads:
        t.join()
    print("all agents finished", flush=True)
