"""Health check for the server's always-on pieces; catches silent failures (e.g. Oct 6 2026: the Kalshi API key
died and the recorder got 401s for 4.5 hours without anyone noticing).

    kalshi-lab health            print the status (server)
    kalshi-lab health --write    also write ~/kalshi-data/health.json (systemd timer, every 2 minutes)
    kalshi-lab health-watch      laptop: poll the server's health.json, macOS notification on change

Checks: the Kalshi feed for each recorded crypto series, spot prices for each (alert only if every exchange is
silent), every configured paper trader (service up and saving results), live traders, the systemd services,
the hourly S3 upload, and disk space.
"""

import argparse
import json
import os
import shutil
import subprocess
import time
from pathlib import Path

from .recorder.config import MARKETS, RECORD_DEFAULT, settlement, stream_name

ROOT = Path(__file__).resolve().parents[2]
RAW = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser()
OUT = RAW.parent / "health.json"
LOG = RAW.parent / "logs" / "kalshi-recorder.log"
SILENT_S = 300        # a feed is down after 5 minutes without data
PAPER_STALE_S = 900   # paper traders save every 5 minutes


def _newest_age(d: Path) -> float | None:
    """Seconds since the newest file under d changed (recordings are one file per hour, appended continuously)."""
    days = sorted(p for p in d.glob("*") if p.is_dir())
    for day in reversed(days[-2:]):
        files = list(day.glob("*"))
        if files:
            return time.time() - max(f.stat().st_mtime for f in files)
    return None


def _active(unit: str) -> bool:
    return subprocess.run(["systemctl", "is-active", "--quiet", unit]).returncode == 0


def check() -> list[str]:
    problems = []
    crypto = [s for s in RECORD_DEFAULT if settlement(s) == "avg60"]  # gold's market hours make silence normal
    login_hint = ""
    if LOG.exists():
        with open(LOG, "rb") as fh:
            fh.seek(max(0, LOG.stat().st_size - 20000))
            if b"HTTP 401" in fh.read():
                login_hint = " (Kalshi is rejecting the login: API key revoked or account deleted?)"
    for s in crypto:
        age = _newest_age(RAW / "kalshi_ws" / s)
        if age is None or age > SILENT_S:
            problems.append(f"Kalshi feed for {s} silent for {'ever' if age is None else f'{age / 60:.0f} min'}{login_hint}")
        ages = [_newest_age(RAW / "spot" / stream_name(f)) for f in MARKETS[s]["live_spot"]]
        fresh = [a for a in ages if a is not None and a <= SILENT_S]
        if not fresh:
            known = [a for a in ages if a is not None]
            problems.append(f"no spot prices for {s} from any exchange " +
                            (f"for {min(known) / 60:.0f} min" if known else "(no recordings found)"))
    for svc in ("kalshi-recorder", "kalshi-dashboard"):
        if not _active(svc):
            problems.append(f"{svc} is not running")
    for conf in sorted((ROOT / "deploy" / "paper").glob("*.json")):
        pid = conf.stem
        if not _active(f"kalshi-paper@{pid}"):
            problems.append(f"paper trader {pid} is not running")
            continue
        runs = sorted((ROOT / "results").glob(f"paper-{pid}-*/summary.json"), key=lambda p: p.stat().st_mtime)
        age = time.time() - runs[-1].stat().st_mtime if runs else None
        # a freshly restarted trader hasn't saved yet; give it one save interval
        if age is not None and age > PAPER_STALE_S:
            problems.append(f"paper trader {pid} hasn't saved results for {age / 60:.0f} min")
    # Live traders run in tmux or a transient systemd unit (no auto-restart, on purpose). Any live log written in the last 2 days means one
    # should be running: alert if its process is gone, it stopped logging, or it halted (stop-loss / KILL file).
    for lg in sorted((RAW.parent / "logs").glob("live-*.log")):
        age = time.time() - lg.stat().st_mtime
        if age > 2 * 86400:
            continue
        name = lg.stem.removeprefix("live-")
        # the log is named by a shorter slug than a variant's folder (live-eth-volfav.log runs strategies/eth-volfav-kelly/)
        alive = subprocess.run(["pgrep", "-f", f"kalshi-lab live strategies/{name}(-[^/]*)?/"],
                               capture_output=True).returncode == 0
        with open(lg, "rb") as fh:
            fh.seek(max(0, lg.stat().st_size - 50000))
            tail = fh.read().decode(errors="replace")
        if not alive:
            problems.append(f"LIVE trader {name} is not running (real money: check ~/kalshi-data/logs/{lg.name})")
        elif age > 300:
            problems.append(f"LIVE trader {name} has not logged for {age / 60:.0f} min")
        if "max_loss hit" in tail or "KILL file present" in tail:
            problems.append(f"LIVE trader {name} halted (stop-loss or KILL file): no new orders")
    # hourly S3 upload (storage.py): the only copy of old recordings once the server trims them
    s3log = RAW.parent / "logs" / "kalshi-s3.log"
    if s3log.exists():
        last = s3log.read_text().strip().splitlines()[-1:] or [""]
        if time.time() - s3log.stat().st_mtime > 3 * 3600:
            problems.append(f"S3 upload hasn't run for {(time.time() - s3log.stat().st_mtime) / 3600:.0f} h")
        elif "ERROR" in last[0] or "error" in last[0]:
            problems.append(f"S3 upload failed: {last[0][:150]}")
    du = shutil.disk_usage(RAW)
    if du.free / du.total < 0.10:
        problems.append(f"disk {du.free / du.total:.0%} free")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab health")
    ap.add_argument("--write", action="store_true", help=f"write {OUT}")
    a = ap.parse_args(argv)
    problems = check()
    now = time.time()
    prev = json.loads(OUT.read_text()) if OUT.exists() else {}
    since = {p: prev.get("since", {}).get(p, now) for p in problems}  # when each problem was first seen
    status = {"checked": now, "ok": not problems, "problems": problems, "since": since}
    if a.write:
        tmp = OUT.with_suffix(".tmp")
        tmp.write_text(json.dumps(status, indent=1))
        tmp.rename(OUT)
    print("OK" if not problems else "PROBLEMS:\n  - " + "\n  - ".join(problems))


def _notify(title: str, msg: str):
    msg = msg.replace('"', "'")[:240]
    subprocess.run(["osascript", "-e", f'display notification "{msg}" with title "{title}" sound name "Basso"'])


def watch(argv=None):
    """Laptop: poll the server's health.json; notify when problems appear, change or clear."""
    ap = argparse.ArgumentParser(prog="kalshi-lab health-watch")
    ap.add_argument("--host", default="kalshi")
    ap.add_argument("--every", type=int, default=120)
    a = ap.parse_args(argv)
    last, offline = None, 0
    while True:
        r = subprocess.run(["ssh", "-o", "ConnectTimeout=10", a.host, "cat kalshi-data/health.json"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            offline += 1
            if offline == 5:  # ~10 minutes: the laptop may just be offline, so only say it once
                _notify("kalshi-lab", "Can't reach the server for 10 minutes.")
        else:
            offline = 0
            h = json.loads(r.stdout)
            if time.time() - h["checked"] > 600:
                h = {"problems": ["the server's health check itself has stopped"]}
            cur = tuple(h["problems"])
            if last is not None and cur != last:
                if cur:
                    _notify("kalshi-lab problem", "; ".join(cur))
                else:
                    _notify("kalshi-lab", "All clear again.")
            elif last is None and cur:
                _notify("kalshi-lab problem", "; ".join(cur))
            last = cur
            print(time.strftime("%H:%M"), "OK" if not cur else cur, flush=True)
        time.sleep(a.every)
