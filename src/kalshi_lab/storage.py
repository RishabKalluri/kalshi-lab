"""S3 holds every byte of data; machines keep only what they need. The bucket mirrors ~/kalshi-data:
raw/ (the recorder's files) and backfill/ (the nightly downloads).

    kalshi-lab s3-push [--dry-run]   trading server, hourly (systemd timer): upload new/changed files, then trim
    kalshi-lab s3-push --dirs backfill --no-trim   research server, after the nightly downloads
    kalshi-lab s3-pull               research server: download everything new, then set file permissions
    pull_data(series)                laptop: download what tests need (remote.py)

The trading server keeps KEEP_BOOK_DAYS of Kalshi books and KEEP_SPOT_DAYS of spot prices (live/paper strategies
can load spot history at startup, live/history.py); older recordings are deleted locally, but only files S3 holds
an identical-size copy of. Nothing ever deletes from S3 (the uploader key can't), and the bucket keeps 30 days of
old versions.
"""

import argparse
import os
import re
import shutil
import subprocess
from datetime import datetime, timedelta, timezone
from pathlib import Path

BUCKET = os.environ.get("KALSHI_S3_BUCKET", "kalshi-data-531080694882")
DATA = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent
KEEP_BOOK_DAYS = 2
KEEP_SPOT_DAYS = 30


def aws() -> str:
    return shutil.which("aws") or str(Path("~/.local/bin/aws").expanduser())


def sync(src: str, dst: str, *extra: str) -> int:
    return subprocess.call([aws(), "s3", "sync", "--only-show-errors", "--no-progress", "--exclude", "*.tmp",
                            src, dst, *extra])


def pull_data(series: list[str]):
    """Bring the downloaded history and every recorded day for `series` (plus spot) here. Incremental: only
    new or grown files are downloaded."""
    s3 = f"s3://{BUCKET}"
    sync(f"{s3}/backfill/", f"{DATA}/backfill/", "--size-only")
    for s in series:
        for kind in ("kalshi_ws", "kalshi_meta"):
            sync(f"{s3}/raw/{kind}/{s}/", f"{DATA}/raw/{kind}/{s}/", "--size-only")
    sync(f"{s3}/raw/spot/", f"{DATA}/raw/spot/", "--size-only")


def _s3_sizes(prefix: str) -> dict[str, int]:
    out = subprocess.run([aws(), "s3api", "list-objects-v2", "--bucket", BUCKET, "--prefix", prefix,
                          "--query", "Contents[].[Key,Size]", "--output", "text"], capture_output=True, text=True)
    if out.returncode != 0:
        raise RuntimeError(f"listing s3://{BUCKET}/{prefix} failed: {out.stderr.strip()}")
    return {k: int(v) for k, v in (ln.split("\t") for ln in out.stdout.splitlines() if "\t" in ln)}


def trim(dry_run: bool = False) -> tuple[int, int]:
    """Delete local recordings older than the keep windows that S3 has; returns (bytes freed, files kept back)."""
    today = datetime.now(timezone.utc).date()
    freed, held = 0, 0
    for kind, keep in (("kalshi_ws", KEEP_BOOK_DAYS), ("spot", KEEP_SPOT_DAYS)):
        cutoff = (today - timedelta(days=keep)).isoformat()
        for day in sorted((DATA / "raw" / kind).glob("*/*")):
            if not day.is_dir() or day.name >= cutoff:
                continue
            rel = day.relative_to(DATA).as_posix()
            remote = _s3_sizes(rel + "/")
            for f in sorted(day.iterdir()):
                size = f.stat().st_size
                if remote.get(f"{rel}/{f.name}") != size:
                    held += 1
                    continue
                if not dry_run:
                    f.unlink()
                freed += size
            if not dry_run and not any(day.iterdir()):
                day.rmdir()
    return freed, held


def _ends_by(path: str, t: datetime) -> bool:
    """A backfilled market file (in the folder of the UTC day it closes) whose events all happen by t (+1s): the market
    closing exactly at the lockbox start is development data although its folder carries the lockbox date."""
    if "/backfill/kalshi/" not in path:
        return False
    import json
    from .recorder.sink import read_lines
    last = None
    for last in read_lines(Path(path)):
        pass
    return last is not None and json.loads(last)["t"] <= int(t.timestamp() + 1) * 10**9  # settled event: close + 1ns


def fix_perms(root: Path = DATA):
    """Research server: agents (and the sandbox's dev runs) may read only development data. Files dated before the
    lockbox start are world-readable; lockbox-dated and undated files only by group kdata (the worker's lockbox runs)."""
    import grp
    from .validate import LOCKBOX_START
    cut = LOCKBOX_START.strftime("%Y-%m-%d")
    gid = grp.getgrnam("kdata").gr_gid
    date = re.compile(r"(\d{4}-\d{2}-\d{2})")
    opened = closed = 0
    for d in ("raw", "backfill"):
        for dirpath, dirs, files in os.walk(root / d):
            for name in [*dirs, *files]:
                p = os.path.join(dirpath, name)
                st = os.lstat(p)
                if name in dirs:
                    mode = 0o2755
                else:
                    m = date.search(p[len(str(root)):])
                    mode = 0o644 if m and (m.group(1) < cut or m.group(1) == cut and _ends_by(p, LOCKBOX_START)) else 0o640
                    opened, closed = opened + (mode == 0o644), closed + (mode == 0o640)
                if st.st_gid != gid:
                    os.chown(p, -1, gid)
                if st.st_mode & 0o7777 != mode:
                    os.chmod(p, mode)
    print(f"permissions: {opened} development files readable, {closed} lockbox/undated files restricted", flush=True)


def pull_all(argv=None):
    os.umask(0o027)  # new files start restricted; fix_perms opens the development ones
    s3 = f"s3://{BUCKET}"
    rc = sync(f"{s3}/raw/", f"{DATA}/raw/", "--size-only") | sync(f"{s3}/backfill/", f"{DATA}/backfill/", "--size-only")
    fix_perms()
    print(f"{datetime.now():%F %T} pulled from S3{' WITH ERRORS' if rc else ''}", flush=True)
    raise SystemExit(rc)


def push(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab s3-push", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dry-run", action="store_true", help="upload, but only report what trimming would delete")
    ap.add_argument("--no-trim", action="store_true")
    ap.add_argument("--dirs", nargs="+", default=["raw", "backfill"], choices=["raw", "backfill"])
    a = ap.parse_args(argv)
    t0 = datetime.now()
    rc = 0
    for d in a.dirs:
        if (DATA / d).is_dir():
            rc |= sync(f"{DATA}/{d}/", f"s3://{BUCKET}/{d}/")
    msg = f"uploaded in {(datetime.now() - t0).seconds}s"
    if rc:
        print(f"{t0:%F %T} {msg} WITH ERRORS (rc={rc}); not trimming", flush=True)
        raise SystemExit(rc)
    if not a.no_trim:
        freed, held = trim(a.dry_run)
        msg += f"; {'would free' if a.dry_run else 'freed'} {freed / 1e9:.2f} GB" + \
               (f", {held} old files not in S3 yet (kept)" if held else "")
    print(f"{t0:%F %T} {msg}", flush=True)


def models_pull(argv=None):
    """Trading server, hourly: bring the monthly model refits (research/refit_live.py, s3://.../models/<slug>/) to
    ~/kalshi-data/models/, where live/paper VolFavorite traders pick them up without a restart."""
    rc = sync(f"s3://{BUCKET}/models/", f"{DATA}/models/", "--exclude", "_*")
    print(f"{datetime.now():%F %T} models pulled{' WITH ERRORS' if rc else ''}", flush=True)
    raise SystemExit(rc)
