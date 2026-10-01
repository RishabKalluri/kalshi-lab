"""Paper trading for any strategy, driven by small config files: deploy/paper/<id>.json
({"strategy": ..., "series": [...], "params": ["k=v", ...]}), one systemd instance each
(kalshi-paper@<id>, from a single template unit).

  laptop:  kalshi-lab paper-start <slug> [-p k=v ...]   write config from strategies/<slug>/config.json, sync, start
           kalshi-lab paper-stop <slug>                    stop it and remove its config
           kalshi-lab paper-list                                 what's paper trading on the server
  server:  kalshi-lab paper-conf <id>                            (what the systemd unit runs)
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CONF = ROOT / "deploy" / "paper"
HOST = "kalshi"


MAX_PAPER = 4  # concurrent paper traders: the server is small and must keep recording smoothly


def _entry(slug: str) -> dict:
    """A strategy folder's config (strategies/<slug>/config.json)."""
    from .strategy_dir import folder_for, load_config
    folder = folder_for(slug)
    if folder is None:
        raise SystemExit(f"no strategy folder strategies/{slug}/ with a config.json")
    c = load_config(folder)
    c["file"] = str((folder / "strategy.py").relative_to(ROOT))
    return c


def conf(argv=None):
    """Server: run the paper trader described by deploy/paper/<id>.json."""
    entry_id = (argv or sys.argv[2:])[0]
    c = json.loads((CONF / f"{entry_id}.json").read_text())
    from .live.run import paper
    extra = ["--sizing", c["sizing"]] if c.get("sizing") else []
    paper([c["strategy"], "--series", *c["series"], *extra, *[x for p in c.get("params", []) for x in ("-p", p)]])


def start(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab paper-start")
    ap.add_argument("id")
    ap.add_argument("-p", "--param", action="append", default=[])
    ap.add_argument("--sizing", help="default: the folder's config.json sizing")
    a = ap.parse_args(argv)
    e = _entry(a.id)
    CONF.mkdir(parents=True, exist_ok=True)
    running = [p.stem for p in CONF.glob("*.json") if p.stem != a.id]
    if len(running) >= MAX_PAPER:
        raise SystemExit(f"{len(running)} paper traders already running ({running}); the limit is {MAX_PAPER}. "
                         "Stop one first or ask the user.")
    conf_ = {"strategy": e["file"], "series": e["series"], "params": a.param or e.get("paper_params", e.get("params", []))}
    if a.sizing or e.get("sizing"):
        conf_["sizing"] = a.sizing or e["sizing"]
    (CONF / f"{a.id}.json").write_text(json.dumps(conf_))
    from .remote import sync
    sync()
    subprocess.check_call(["ssh", HOST, f"sudo systemctl enable --now kalshi-paper@{a.id} && sudo systemctl restart kalshi-paper@{a.id}"
                                        f" && systemctl is-active kalshi-paper@{a.id}"])
    print(f"paper trading {e.get('name', a.id)} on the server as kalshi-paper@{a.id}")


def stop(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab paper-stop")
    ap.add_argument("id")
    a = ap.parse_args(argv)
    subprocess.call(["ssh", HOST, f"sudo systemctl disable --now kalshi-paper@{a.id}"])
    (CONF / f"{a.id}.json").unlink(missing_ok=True)
    from .remote import sync
    sync()
    print(f"stopped kalshi-paper@{a.id} (its results stay in results/)")


def list_(argv=None):
    subprocess.call(["ssh", HOST, "systemctl list-units 'kalshi-paper@*' --no-legend --plain | awk '{print $1, $3, $4}'"])
