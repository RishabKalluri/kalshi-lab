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
import os
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
    if os.environ.get("KALSHI_SITE") == "research":
        return _test_research(a)
    if not os.environ.get("KALSHI_LOCAL_TESTS"):
        sys.exit("Tests run on the research server now (one ledger, sandboxed; deploy/research/). Strategy agents run "
                 "there too: ask Claude to start one. (KALSHI_LOCAL_TESTS=1 forces a local run that the official "
                 "ledger never sees.)")
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


def _test_research(a):
    """Research server: every stage, smoke included, runs in the worker's sandbox (deploy/research/); the data is
    already here. Queue the job; with --wait, block until it finishes."""
    from .jobs import enqueue
    from .strategy_dir import folder_for
    folder = folder_for(a.strategy)
    if folder is None:
        sys.exit("tests need a strategy folder (strategies/<slug>): kalshi-lab new <slug>")
    job = f"{folder.name}-{datetime.now():%m%d-%H%M%S}"
    stages = ([] if a.skip_smoke else ["smoke"]) + [s for s in a.stages.split(",") if s]
    enqueue([a.strategy, *(["--series", *a.series] if a.series else []), *[x for p in a.param for x in ("-p", p)],
             "--stages", ",".join(stages), "--job", job, "--note", a.note])
    print(f"queued {job}; results appear in the dashboard as stages finish.")
    if a.wait:
        wait(job)
    elif not a.stages and not wait(job, 540):  # smoke only: wait like the laptop's foreground smoke, under 10 min
        sys.exit(3)


def wait_cmd(argv=None):
    """`kalshi-lab wait <job> [--minutes M]`: wait up to M minutes (default 9, under agents' 10-minute command limit)
    for a queued job; prints its verdicts when done, else where it is (exit 3: still queued/running, call again)."""
    import argparse
    ap = argparse.ArgumentParser(prog="kalshi-lab wait")
    ap.add_argument("job")
    ap.add_argument("--minutes", type=float, default=9)
    a = ap.parse_args(argv)
    if not wait(a.job, a.minutes * 60):
        sys.exit(3)


def wait(job: str, timeout: float | None = None) -> bool:
    """Block until a job finishes (or `timeout` seconds pass: returns False); print each stage's verdict and the job
    status (for agents)."""
    import json
    import time
    q = ROOT / "results" / "_jobs"
    done = q / "done" / f"{job}.json"
    t0 = time.time()
    while not done.exists():
        if timeout is not None and time.time() - t0 > timeout:
            if (q / "running" / f"{job}.json").exists():
                where = "running: " + json.loads((q / "running" / f"{job}.json").read_text()).get("stage", "?")
            elif (q / "queue" / f"{job}.json").exists():
                from .jobs import _smoke_only  # the worker's order: smoke-only jobs first, then oldest first
                key = lambda p: (not _smoke_only(p), p.stat().st_mtime)  # noqa: E731
                me = key(q / "queue" / f"{job}.json")
                ahead = sum(key(p) < me for p in (q / "queue").glob("*.json")) + len(list((q / "running").glob("*.json")))
                where = f"queued, {ahead} job(s) ahead"
            else:
                where = "unknown job"
            print(f"job {job}: still {where}; call `kalshi-lab wait {job}` again (meanwhile, work on something else)")
            return False
        time.sleep(15)
    j = json.loads(done.read_text())
    for stage in j["stages"]:
        rep = ROOT / "results" / "_jobs" / f"{job}.{stage}.json"
        if rep.exists():
            r = json.loads(rep.read_text())
            pooled = r["cards"].get("POOLED") or next(iter(r["cards"].values()), {})
            print(f"{stage}: verdict={r['verdict']} pooled={pooled}")
    print(f"job {job}: {j['status']}")
    if j["status"] == "failed":
        print("log tail:\n" + j.get("log_tail", "")[-1500:])
    return True


def pull(argv=None):
    """`kalshi-lab pull SERIES ...`: download the history + recordings for these series from S3."""
    import argparse
    ap = argparse.ArgumentParser(prog="kalshi-lab pull")
    ap.add_argument("series", nargs="+")
    a = ap.parse_args(argv)
    if os.environ.get("KALSHI_SITE") == "research":
        print("the research server syncs all data from S3 automatically (hourly); nothing to pull")
        return
    pull_data(a.series)
    print(f"pulled {a.series}")
