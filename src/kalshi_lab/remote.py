"""Laptop side: `kalshi-lab test <strategy> --series ... [-p ...]`.

Tests are compute-bound and the server's CPU is burstable (measured ~30x slower than this laptop once
throttled), so tests run HERE by default and results are pushed to the server for the dashboard:
1. pulls the data the tests need from the server (backfill history + recent recorded books),
2. runs smoke locally (seconds),
3. if it passes, queues quick + full for the local background worker (tmux session kalshi-worker),
   which pushes job state and results to the server as it goes.
`--on-server` runs everything on the server instead (useful when the laptop will be closed).
"""

import argparse
import shlex
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HOST = "kalshi"
UV = "~/.local/bin/uv"


def sync():
    subprocess.check_call(["rsync", "-az", "--delete", "--exclude", ".venv", "--exclude", "results", "--exclude",
                           "__pycache__", "--exclude", ".git", "--exclude", "research/data", "./", f"{HOST}:kalshi/"], cwd=ROOT)


def remote(cmd: str) -> int:
    return subprocess.call(["ssh", HOST, f"cd ~/kalshi && {UV} run -q kalshi-lab {cmd}"])


def pull_data(series: list[str], recorded_days: int = 2):
    """Bring the server's backfill + the last few days of recorded books for `series` to this laptop."""
    data = Path("~/kalshi-data").expanduser()
    subprocess.call(["rsync", "-az", f"{HOST}:kalshi-data/backfill/", f"{data}/backfill/"])
    from datetime import datetime, timedelta, timezone
    days = [(datetime.now(timezone.utc) - timedelta(days=d)).strftime("%Y-%m-%d") for d in range(recorded_days + 1)]
    inc = ["--include=*/"] + [f"--include=kalshi_*/{s}/{d}/**" for s in series for d in days] + \
          [f"--include=spot/*/{d}/**" for d in days] + ["--exclude=*"]
    subprocess.call(["rsync", "-az", "--prune-empty-dirs", *inc, f"{HOST}:kalshi-data/raw/", f"{data}/raw/"])


def ensure_local_worker():
    if subprocess.call(["tmux", "has-session", "-t", "kalshi-worker"], stderr=subprocess.DEVNULL) != 0:
        subprocess.check_call(["tmux", "new-session", "-d", "-s", "kalshi-worker", "-c", str(ROOT),
                               f"caffeinate -ims uv run kalshi-lab worker --push {HOST} >> "
                               f"{Path('~/kalshi-data/logs').expanduser()}/worker-local.log 2>&1"])


def test(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab test", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("strategy")
    ap.add_argument("--series", nargs="+", default=["KXBTC15M"])
    ap.add_argument("-p", "--param", action="append", default=[])
    ap.add_argument("--stages", default="quick,full", help="background stages to queue after smoke")
    ap.add_argument("--skip-smoke", action="store_true")
    ap.add_argument("--on-server", action="store_true", help="run the stages on the server instead of this laptop")
    a = ap.parse_args(argv)
    if not a.on_server:
        return _test_local(a)
    job = f"{Path(a.strategy.split(':')[0]).stem}-{datetime.now():%m%d-%H%M%S}"
    params = "".join(f" -p {shlex.quote(p)}" for p in a.param)
    series = " ".join(a.series)
    print(f"syncing code to {HOST}...", flush=True)
    sync()
    if not a.skip_smoke:
        print("smoke test on the server:", flush=True)
        rc = remote(f"validate smoke {shlex.quote(a.strategy)} --series {series}{params} --job {job}")
        if rc != 0:
            print("smoke failed: fix it and re-run. Nothing was queued.")
            sys.exit(rc)
    remote(f"enqueue {shlex.quote(a.strategy)} --series {series}{params} --stages {a.stages} --job {job}")
    print(f"\nqueued in the background. Check with:  uv run kalshi-lab jobs   or the dashboard (deploy/dashboard.sh)")


def jobs(argv=None):
    if Path("/etc/systemd/system/kalshi-worker.service").exists():  # on the server itself
        from .jobs import list_jobs
        return list_jobs(argv)
    sys.exit(remote("jobs-local"))


def _test_local(a):
    job = f"{Path(a.strategy.split(':')[0]).stem}-{datetime.now():%m%d-%H%M%S}"
    print(f"pulling data for {a.series} from {HOST}...", flush=True)
    pull_data(a.series)
    sync()  # the server's dashboard reads strategy files/registry
    base = [sys.executable, "-m", "kalshi_lab"]
    params = [x for p in a.param for x in ("-p", p)]
    if not a.skip_smoke:
        print("smoke test (local):", flush=True)
        rc = subprocess.call(base + ["validate", "smoke", a.strategy, "--series", *a.series, *params, "--job", job], cwd=ROOT)
        if rc != 0:
            print("smoke failed: fix it and re-run. Nothing was queued.")
            sys.exit(rc)
        subprocess.call(["rsync", "-az", *[str(p) for p in (ROOT / "results").glob(f"{job}-smoke")],
                         f"{HOST}:kalshi/results/"], stdout=subprocess.DEVNULL)
    subprocess.check_call(base + ["enqueue", a.strategy, "--series", *a.series, *params, "--stages", a.stages,
                                  "--job", job], cwd=ROOT)
    ensure_local_worker()
    print("queued on this laptop's background worker; results appear in the dashboard as they finish.")
