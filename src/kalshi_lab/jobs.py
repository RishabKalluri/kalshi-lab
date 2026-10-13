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
# Research server: strategy code (written by agents) runs only inside kalshi-sandbox, as a user that can't write the
# ledger or read lockbox data (dev stages) / can't leave anything an agent could read (lockbox). This worker, the
# trusted side, checks the rules first and records the result itself. See deploy/research/.
SANDBOX = os.environ.get("KALSHI_SANDBOX") == "1"


def _dirs():
    for d in ("queue", "running", "done"):
        (Q / d).mkdir(parents=True, exist_ok=True)


def _smoke_only(p: Path) -> bool:
    try:
        return json.loads(p.read_text()).get("stages") == ["smoke"]
    except (OSError, ValueError):
        return False


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
                note=a.note, created=datetime.now(timezone.utc).isoformat(), status="queued",
                agent_run=os.environ.get("KALSHI_AGENT_RUN", ""))  # which autonomous agent run queued it (agents.py)
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
    """Copy job state and results to the trading server so its dashboard shows them. Laptop: straight into its repo
    (host:kalshi/...). Research server: KALSHI_PUSH_PREFIX="" and an SSH key that can only write the trading server's
    drop folder (rrsync), which it merges itself (research_sync.py); then whole strategy folders go too."""
    if not host:
        return
    pre = os.environ.get("KALSHI_PUSH_PREFIX", "kalshi/")
    quiet = dict(stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    subprocess.call(["rsync", "-az", "--exclude", "running/", f"{Q}/", f"{host}:{pre}results/_jobs/"], **quiet)
    subprocess.call(["rsync", "-az", "--delete", f"{Q}/running/", f"{host}:{pre}results/_jobs/running/"], **quiet)
    ledger = ROOT / "results" / "_ledger"
    if ledger.exists():  # the authoritative records: the server's dashboard verifies results.json against them
        subprocess.call(["rsync", "-az", f"{ledger}/", f"{host}:{pre}results/_ledger/"], **quiet)
    if job_id:
        from .strategy_dir import folder_for
        # the job's results.json too, so the server's copy and its ledger always agree (the dashboard checks)
        job = next((json.loads(f.read_text()) for d in ("running", "done") for f in [Q / d / f"{job_id}.json"]
                    if f.exists()), None)
        folder = folder_for(job["strategy"]) if job else None
        if folder and SANDBOX:
            subprocess.call(["rsync", "-az", "--exclude", "__pycache__", "--exclude", ".params-held*", f"{folder}/",
                             f"{host}:{pre}strategies/{folder.name}/"], **quiet)
        elif folder and (folder / "results.json").exists():
            subprocess.call(["rsync", "-az", str(folder / "results.json"),
                             f"{host}:{pre}{folder.relative_to(ROOT)}/results.json"], **quiet)
        dirs = [str(p) for d in ("", "_lockbox") for p in (ROOT / "results" / d).glob(f"{job_id}-*") if p.is_dir()]
        if dirs:
            subprocess.call(["rsync", "-az", *dirs, f"{host}:{pre}results/"], **quiet)


def _sandboxed(j: dict, stage: str, log):
    """Prepare one sandboxed stage: run the rule checks here, then return (command, finish(rc) -> rc)."""
    import shutil
    from .strategy_dir import append_result, code_hash, folder_for, ledger_append
    folder = folder_for(j["strategy"])
    if folder is None:
        log.write("research server: tests need a strategy folder (strategies/<slug>)\n")
        return None, lambda rc: 2
    args = ["validate", stage, j["strategy"], "--series", *j["series"], "--job", j["id"], "--note", j.get("note", "")] + \
           [x for p in j["params"] for x in ("-p", p)]
    rc = subprocess.call([sys.executable, "-m", "kalshi_lab", *args, "--preflight"], cwd=ROOT, stdout=log,
                         stderr=subprocess.STDOUT)
    if rc != 0:
        return None, lambda _: rc
    code = code_hash(folder)  # fingerprint taken here, not by the code under test
    kind = "lockbox" if stage == "lockbox" else "dev"
    out = ROOT / "results" / "_sandbox" / f"{j['id']}.{stage}"
    shutil.rmtree(out, ignore_errors=True)
    out.mkdir(parents=True)
    held = folder / f".params-held-{j['id']}"
    if kind == "lockbox":  # fit() must regenerate params/ from this code; a fresh params/ only the sandbox can read
        shutil.chown(out, group="kdata")
        out.chmod(0o2770)
        if (folder / "params").exists():
            (folder / "params").rename(held)
        (folder / "params").mkdir()
        shutil.chown(folder / "params", group="kdata")
        (folder / "params").chmod(0o2770)
    else:
        out.chmod(0o2775)

    def finish(rc: int) -> int:
        if kind == "lockbox":
            shutil.rmtree(folder / "params", ignore_errors=True)
            if held.exists():
                held.rename(folder / "params")
        rep = out / "report.json"
        if rep.exists():
            shutil.copyfile(rep, Q / f"{j['id']}.{stage}.json")
        rec_f = out / "record.json"
        if rec_f.exists():
            rec = json.loads(rec_f.read_text())
            rec.update(stage=stage, job=j["id"], code=code, params=j["params"])
            append_result(folder, ledger_append(folder.name, rec))
        shutil.rmtree(out, ignore_errors=True)
        return rc
    return ["sudo", "-n", "/usr/local/sbin/kalshi-sandbox", kind, folder.name, str(out), "--", *args], finish


def _code_stamp() -> float:
    """Latest modification time of the package's code (the worker restarts itself when it changes)."""
    return max(p.stat().st_mtime for p in (ROOT / "src" / "kalshi_lab").rglob("*.py"))


def worker(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab worker")
    ap.add_argument("--push", help="ssh host to copy job state/results to after each step (laptop worker)")
    a = ap.parse_args(argv)
    _dirs()
    print("worker started", flush=True)
    for f in (Q / "running").glob("*.json"):  # jobs interrupted by a restart go back in the queue
        f.rename(Q / "queue" / f.name)
    started_code = _code_stamp()
    while True:
        # oldest first, but smoke-only jobs (about a minute) jump ahead of quick/full tests
        queued = sorted((Q / "queue").glob("*.json"), key=lambda p: (not _smoke_only(p), p.stat().st_mtime))
        if not queued:
            if _code_stamp() != started_code:  # code changed while idle: restart so jobs never run stale code
                print("code changed: restarting worker", flush=True)
                os.execv(sys.executable, [sys.executable, "-m", "kalshi_lab", "worker"] +
                         (["--push", a.push] if a.push else []))
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
                finish = None
                if SANDBOX:
                    cmd, finish = _sandboxed(j, stage, log)
                    log.flush()
                    if cmd is None:
                        ok = False
                        break
                proc = subprocess.Popen(cmd, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)
                cancel = Q / f"{j['id']}.cancel"
                last_push = 0.0
                while proc.poll() is None:  # poll so a cancel request can stop the whole process group
                    if cancel.exists():
                        if SANDBOX:  # the sandbox runs as root-managed systemd unit: ask it to stop
                            subprocess.call(["sudo", "-n", "/usr/local/sbin/kalshi-sandbox", "stop", j["id"], stage])
                        else:
                            os.killpg(proc.pid, signal.SIGTERM)
                        proc.wait()
                        break
                    if a.push and time.time() - last_push > 30:
                        log.flush()
                        _push(a.push)
                        last_push = time.time()
                    time.sleep(2)
                if finish:
                    finish(proc.returncode)
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
