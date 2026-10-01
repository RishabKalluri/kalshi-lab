"""Paper trading for any strategy, driven by small config files: deploy/paper/<id>.json
({"strategy": ..., "series": [...], "params": ["k=v", ...]}), one systemd instance each
(kalshi-paper@<id>, from a single template unit).

  laptop:  kalshi-lab paper-start <registry-id> [-p k=v ...]   write config, sync, start it on the server
           kalshi-lab paper-stop <registry-id>                  stop it and remove its config
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


def _registry(entry_id: str) -> dict:
    reg = json.loads((ROOT / "strategies" / "registry.json").read_text())
    for e in reg:
        if e["id"] == entry_id:
            return e
    raise SystemExit(f"no strategy '{entry_id}' in strategies/registry.json")


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
    ap.add_argument("--sizing", help="e.g. pct:0.5 (default: the global default, pct:1)")
    a = ap.parse_args(argv)
    e = _registry(a.id)
    if not e.get("file"):
        raise SystemExit(f"{a.id} has no strategy file yet")
    CONF.mkdir(parents=True, exist_ok=True)
    conf_ = {"strategy": e["file"], "series": e["series"], "params": a.param}
    if a.sizing:
        conf_["sizing"] = a.sizing
    (CONF / f"{a.id}.json").write_text(json.dumps(conf_))
    from .remote import sync
    sync()
    subprocess.check_call(["ssh", HOST, f"sudo systemctl enable --now kalshi-paper@{a.id} && sudo systemctl restart kalshi-paper@{a.id}"
                                        f" && systemctl is-active kalshi-paper@{a.id}"])
    print(f"paper trading {e['name']} on the server as kalshi-paper@{a.id}")


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
