"""A tiny file-based job queue for background validation on the server.

  results/_jobs/queue/<id>.json      waiting
  results/_jobs/running/<id>.json    being worked on (one at a time: the server has 2 vCPUs and also paper trades)
  results/_jobs/done/<id>.json       finished (status ok/failed, log tail); stage reports: results/_jobs/<id>.<stage>.json

  kalshi-lab enqueue <strategy> --series ... [-p ...] [--stages quick,full]   (server side; `test` calls this over ssh)
  kalshi-lab jobs                                                            list jobs
  kalshi-lab worker                                                          the systemd service loop
"""

import argparse
import json
import os
import signal
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
Q = ROOT / "results" / "_jobs"


def _dirs():
    for d in ("queue", "running", "done"):
        (Q / d).mkdir(parents=True, exist_ok=True)


def enqueue(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab enqueue")
    ap.add_argument("strategy")
    ap.add_argument("--series", nargs="+", help="default: the strategy folder's config.json")
    ap.add_argument("-p", "--param", action="append", default=[])
    ap.add_argument("--stages", default="quick,full")
    ap.add_argument("--job")
    ap.add_argument("--note", default="")
    a = ap.parse_args(argv)
    _dirs()
    from .strategy_dir import folder_for, load_config
    folder = folder_for(a.strategy)
    series = a.series or (load_config(folder)["series"] if folder else ["KXBTC15M"])
    slug = folder.name if folder else Path(a.strategy.split(":")[0]).stem
    job = a.job or f"{slug}-{datetime.now():%m%d-%H%M%S}"
    spec = dict(id=job, strategy=a.strategy, series=series, params=a.param, stages=a.stages.split(","),
                note=a.note, created=datetime.now(timezone.utc).isoformat(), status="queued")
    (Q / "queue" / f"{job}.json").write_text(json.dumps(spec, indent=1))
    print(f"queued {job}: {a.stages} for {a.strategy} on {a.series}")


def list_jobs(argv=None):
    _dirs()
    rows = []
    for state in ("running", "queue", "done"):
        for f in sorted((Q / state).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
            j = json.loads(f.read_text())
            v = ""
            rep = Q / f"{j['id']}.full.json"
            if rep.exists():
                v = json.loads(rep.read_text())["verdict"]
            rows.append((state, j["id"], j.get("status", ""), j.get("stage", ""), v, j["strategy"], ",".join(j["series"])))
    if not rows:
        print("no jobs")
    for r in rows[:30]:
        print(f"{r[0]:<8} {r[1]:<36} {r[2]:<8} {r[3]:<6} {r[4]:<13} {r[5]} [{r[6]}]")


def _push(host: str | None, job_id: str | None = None):
    """Laptop worker: copy job state and results to the server so its dashboard shows them."""
    if not host:
        return
    subprocess.call(["rsync", "-az", f"{Q}/", f"{host}:kalshi/results/_jobs/"], stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL)
    ledger = ROOT / "results" / "_ledger"
    if ledger.exists():  # the authoritative records: the server's dashboard verifies results.json against them
        subprocess.call(["rsync", "-az", f"{ledger}/", f"{host}:kalshi/results/_ledger/"], stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL)
    if job_id:
        dirs = [str(p) for p in (ROOT / "results").glob(f"{job_id}-*") if p.is_dir()]
        if dirs:
            subprocess.call(["rsync", "-az", *dirs, f"{host}:kalshi/results/"], stdout=subprocess.DEVNULL,
                            stderr=subprocess.DEVNULL)


def worker(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab worker")
    ap.add_argument("--push", help="ssh host to copy job state/results to after each step (laptop worker)")
    a = ap.parse_args(argv)
    _dirs()
    print("worker started", flush=True)
    for f in (Q / "running").glob("*.json"):  # jobs interrupted by a restart go back in the queue
        f.rename(Q / "queue" / f.name)
    while True:
        queued = sorted((Q / "queue").glob("*.json"), key=lambda p: p.stat().st_mtime)
        if not queued:
            time.sleep(5)
            continue
        f = queued[0].rename(Q / "running" / queued[0].name)
        j = json.loads(f.read_text())
        j["status"], j["started"] = "running", datetime.now(timezone.utc).isoformat()
        log_path = ROOT / "results" / "_jobs" / f"{j['id']}.log"
        ok = True
        with open(log_path, "a") as log:
            for stage in j["stages"]:
                j["stage"] = stage
                f.write_text(json.dumps(j, indent=1))
                cmd = [sys.executable, "-m", "kalshi_lab", "validate", stage, j["strategy"], "--series", *j["series"],
                       "--job", j["id"], "--note", j.get("note", "")] + [x for p in j["params"] for x in ("-p", p)]
                log.write(f"\n=== {stage} {datetime.now(timezone.utc):%H:%M:%S} ===\n")
                log.flush()
                proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                cancel = Q / f"{j['id']}.cancel"
                last_push = 0.0
                while proc.poll() is None:  # poll so a cancel request can stop the whole process group
                    if cancel.exists():
                        os.killpg(proc.pid, signal.SIGTERM)
                        proc.wait()
                        break
                    if a.push and time.time() - last_push > 30:
                        log.flush()
                        _push(a.push)
                        last_push = time.time()
                    time.sleep(2)
                _push(a.push, j["id"])
                if proc.returncode == 4:  # quick gate: clearly negative, don't spend CPU on the full test
                    j["gated"] = stage
                    break
                if cancel.exists() or proc.returncode != 0:
                    ok = False
                    break
        cancelled = (Q / f"{j['id']}.cancel").exists()
        j["status"] = "cancelled" if cancelled else ("rejected at quick" if j.get("gated") else ("ok" if ok else "failed"))
        j["finished"] = datetime.now(timezone.utc).isoformat()
        j["log_tail"] = log_path.read_text()[-2000:]
        (Q / "done" / f.name).write_text(json.dumps(j, indent=1))
        f.unlink()
        if a.push:  # the server copy of the running file must go too
            subprocess.call(["ssh", a.push, f"rm -f kalshi/results/_jobs/running/{f.name}"], stdout=subprocess.DEVNULL)
        _push(a.push, j["id"])
        print(f"{j['id']}: {j['status']}", flush=True)


def cancel(argv=None):
    """kalshi-lab cancel <job-id>: stop a queued or running job."""
    ap = argparse.ArgumentParser(prog="kalshi-lab cancel")
    ap.add_argument("job")
    a = ap.parse_args(argv)
    _dirs()
    q = Q / "queue" / f"{a.job}.json"
    if q.exists():
        j = json.loads(q.read_text())
        j["status"] = "cancelled"
        (Q / "done" / q.name).write_text(json.dumps(j, indent=1))
        q.unlink()
        print(f"removed {a.job} from the queue")
        return
    (Q / f"{a.job}.cancel").write_text(datetime.now(timezone.utc).isoformat())
    print(f"cancel requested for {a.job}; the worker stops it within a few seconds")
