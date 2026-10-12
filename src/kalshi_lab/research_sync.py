"""Trading server: merge what the research server pushed into its drop folder (~/lab-inbox) into this repo, so the
dashboard shows the research server's jobs, ledger and strategies.

    kalshi-lab research-merge      (systemd timer, every 2 minutes)

The research server's key can only write ~/lab-inbox (rrsync), never this repo, and this merge never touches what
trades here: results of paper/live runs, and strategy folders that are paper/live or deployed (deploy/paper/).
"""

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INBOX = Path("~/lab-inbox").expanduser()


def _protected() -> set[str]:
    slugs = set()
    for p in (ROOT / "strategies").glob("*/config.json"):
        try:
            if json.loads(p.read_text()).get("status") in ("paper", "live"):
                slugs.add(p.parent.name)
        except ValueError:
            slugs.add(p.parent.name)
    for c in (ROOT / "deploy" / "paper").glob("*.json"):
        slugs.add(Path(json.loads(c.read_text())["strategy"]).parent.name)
    return slugs


def merge(argv=None):
    res = INBOX / "results"
    if res.is_dir():
        subprocess.call(["rsync", "-a", "--exclude", "/paper-*", "--exclude", "/live-*", "--exclude", "/_jobs/running/",
                         f"{res}/", f"{ROOT}/results/"])
        if (res / "_jobs" / "running").is_dir():
            subprocess.call(["rsync", "-a", "--delete", f"{res}/_jobs/running/", f"{ROOT}/results/_jobs/running/"])
    keep = _protected()
    for d in sorted((INBOX / "strategies").glob("*")):
        if d.is_dir() and not d.name.startswith((".", "_")) and d.name not in keep:
            subprocess.call(["rsync", "-a", f"{d}/", f"{ROOT}/strategies/{d.name}/"])
