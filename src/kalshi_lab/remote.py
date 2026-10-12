"""Laptop side: `kalshi-lab test <strategy> --series ... [-p ...]`.

Tests are compute-bound and the server's CPU is burstable (measured ~30x slower than this laptop once
throttled), so tests run HERE by default and results are pushed to the server for the dashboard:
1. pulls the data the tests need from S3 (backfill history + recorded books; see storage.py),
2. runs smoke locally (seconds),
3. if it passes, queues quick + full for the local background worker (tmux session kalshi-worker),
   which pushes job state and results to the server as it goes.
The trading server keeps only the last 2 days of books (storage.py), so tests never run there.
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


def pull_data(series: list[str]):
    """Bring the downloaded history + every recorded day for `series` to this laptop, from S3 (storage.py)."""
    from .storage import pull_data as s3_pull
    s3_pull(series)


def ensure_local_worker():
    if subprocess.call(["tmux", "has-session", "-t", "kalshi-worker"], stderr=subprocess.DEVNULL) != 0:
        subprocess.check_call(["tmux", "new-session", "-d", "-s", "kalshi-worker", "-c", str(ROOT),
                               f"caffeinate -ims uv run kalshi-lab worker --push {HOST} >> "
                               f"{Path('~/kalshi-data/logs').expanduser()}/worker-local.log 2>&1"])


def test(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab test", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("strategy", help="strategy folder/slug (e.g. eth-volfav) or a .py file")
    ap.add_argument("--series", nargs="+", help="default: the strategy folder's config.json")
    ap.add_argument("--note", default="", help="what changed in this iteration (logged to results.json)")
    ap.add_argument("--wait", action="store_true", help="block until the queued stages finish, then print the verdicts")
    ap.add_argument("-p", "--param", action="append", default=[])
    ap.add_argument("--stages", default="quick,full", help="background stages to queue after smoke")
    ap.add_argument("--skip-smoke", action="store_true")
    ap.add_argument("--on-server", action="store_true", help="run the stages on the server instead of this laptop")
    a = ap.parse_args(argv)
    if not a.on_server:
        return _test_local(a)
    sys.exit("--on-server is retired: the trading server keeps only 2 days of recorded books (the rest is in S3), "
             "so its results would differ. Tests run on this laptop (the research server is next).")
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
    from .strategy_dir import folder_for, load_config
    folder = folder_for(a.strategy)
    if not a.series:
        a.series = load_config(folder)["series"] if folder else ["KXBTC15M"]
    slug = folder.name if folder else Path(a.strategy.split(":")[0]).stem
    job = f"{slug}-{datetime.now():%m%d-%H%M%S}"
    print(f"pulling data for {a.series} from S3...", flush=True)
    pull_data(a.series)
    sync()  # the server's dashboard reads strategy files/registry
    base = [sys.executable, "-m", "kalshi_lab"]
    params = [x for p in a.param for x in ("-p", p)]
    if not a.skip_smoke:
        print("smoke test (local):", flush=True)
        rc = subprocess.call(base + ["validate", "smoke", a.strategy, "--series", *a.series, *params, "--job", job,
                                     "--note", a.note], cwd=ROOT)
        if rc != 0:
            print("smoke failed: fix it and re-run. Nothing was queued.")
            sys.exit(rc)
        subprocess.call(["rsync", "-az", *[str(p) for p in (ROOT / "results").glob(f"{job}-smoke")],
                         f"{HOST}:kalshi/results/"], stdout=subprocess.DEVNULL)
        subprocess.call(["rsync", "-az", f"{ROOT}/results/_ledger/", f"{HOST}:kalshi/results/_ledger/"],
                        stdout=subprocess.DEVNULL)
    if not a.stages:
        return
    subprocess.check_call(base + ["enqueue", a.strategy, "--series", *a.series, *params, "--stages", a.stages,
                                  "--job", job, "--note", a.note], cwd=ROOT)
    ensure_local_worker()
    print(f"queued {job} ({a.stages}) on this laptop's background worker; results appear in the dashboard as they finish.")
    if a.wait:
        wait(job)


def wait(job: str):
    """Block until a job finishes; print each stage's verdict and the job status (for agents)."""
    import json
    import time
    done = ROOT / "results" / "_jobs" / "done" / f"{job}.json"
    while not done.exists():
        time.sleep(15)
    j = json.loads(done.read_text())
    for stage in j["stages"]:
        rep = ROOT / "results" / "_jobs" / f"{job}.{stage}.json"
        if rep.exists():
            r = json.loads(rep.read_text())
            pooled = r["cards"].get("POOLED") or next(iter(r["cards"].values()), {})
            print(f"{stage}: verdict={r['verdict']} pooled={pooled}")
    print(f"job {job}: {j['status']}")


def pull(argv=None):
    """`kalshi-lab pull SERIES ...`: download the history + recordings for these series from S3."""
    import argparse
    ap = argparse.ArgumentParser(prog="kalshi-lab pull")
    ap.add_argument("series", nargs="+")
    a = ap.parse_args(argv)
    pull_data(a.series)
    print(f"pulled {a.series}")
