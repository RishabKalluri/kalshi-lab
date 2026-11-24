"""Backfill through the current run's start, then checkpoint after uploading."""

import subprocess
import sys
from datetime import datetime, timedelta, timezone

from kalshi_lab.storage import DATA

SERIES = ("KXBTC15M", "KXETH15M", "KXSOL15M", "KXGOLD15M", "KXXRP15M", "KXDOGE15M")
OVERLAP = timedelta(days=3)


def main():
    logs = DATA / "logs"
    checkpoint = logs / "nightly-backfill-through"
    end = datetime.now(timezone.utc)
    try:
        through = datetime.fromisoformat(checkpoint.read_text().strip())
    except FileNotFoundError:
        # On upgrade, use the timestamp from the old nightly job's last successful upload.
        through = end
        legacy = logs / "nightly.log"
        if legacy.exists():
            with legacy.open() as log:
                for line in log:
                    if line[19:].startswith(" uploaded in ") and line.rstrip().endswith("s"):
                        through = datetime.fromisoformat(line[:19]).astimezone(timezone.utc)
    start = min(through, end) - OVERLAP
    subprocess.check_call([
        sys.executable, "-m", "kalshi_lab", "backfill", "--series", *SERIES,
        "--start", start.isoformat(), "--end", end.isoformat(), "--strict",
    ])
    subprocess.check_call([sys.executable, "-m", "kalshi_lab", "s3-push", "--dirs", "backfill", "--no-trim"])
    tmp = checkpoint.with_suffix(".tmp")
    tmp.write_text(end.isoformat() + "\n")
    tmp.replace(checkpoint)


if __name__ == "__main__":
    main()
