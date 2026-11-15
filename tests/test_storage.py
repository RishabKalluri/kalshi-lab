import json
import subprocess
from datetime import datetime, timedelta, timezone

import pytest
import zstandard

from kalshi_lab import storage

TODAY = datetime.now(timezone.utc).date()


def day(n: int) -> str:
    return (TODAY - timedelta(days=n)).isoformat()


class FakeBucket(dict):
    def __init__(self):
        super().__init__()
        self.calls: list[str] = []

    def sizes(self, prefix: str) -> dict[str, int]:
        self.calls.append(prefix)
        return {k: v for k, v in self.items() if k.startswith(prefix)}


@pytest.fixture
def s3(tmp_path, monkeypatch):
    """Point storage at tmp_path and fake the bucket listing with a {key: size} dict."""
    remote = FakeBucket()
    monkeypatch.setattr(storage, "DATA", tmp_path)
    monkeypatch.setattr(storage, "_s3_sizes", remote.sizes)
    return remote


def put(root, rel: str, data: bytes = b"x" * 10):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_bytes(data)
    return p


def test_trim_deletes_old_files_only_when_s3_size_matches(tmp_path, s3):
    old = day(storage.KEEP_BOOK_DAYS + 1)
    match = put(tmp_path, f"raw/kalshi_ws/KXETH15M/{old}/00.jsonl.zst", b"a" * 7)
    differ = put(tmp_path, f"raw/kalshi_ws/KXETH15M/{old}/01.jsonl.zst", b"b" * 5)
    missing = put(tmp_path, f"raw/kalshi_ws/KXETH15M/{old}/02.jsonl.zst", b"c" * 3)
    s3[f"raw/kalshi_ws/KXETH15M/{old}/00.jsonl.zst"] = 7
    s3[f"raw/kalshi_ws/KXETH15M/{old}/01.jsonl.zst"] = 4

    freed, held = storage.trim()

    assert (freed, held) == (7, 2)
    assert not match.exists()
    assert differ.exists() and missing.exists()
    assert match.parent.is_dir()  # still holds unsynced files


def test_trim_leaves_files_within_keep_window(tmp_path, s3):
    files = [put(tmp_path, f"raw/kalshi_ws/KXETH15M/{day(n)}/00.jsonl.zst") for n in range(storage.KEEP_BOOK_DAYS + 1)]
    files += [put(tmp_path, f"raw/spot/coinbase/{day(n)}/00.jsonl.zst") for n in (0, storage.KEEP_SPOT_DAYS)]
    for f in files:
        s3[f.relative_to(tmp_path).as_posix()] = f.stat().st_size

    assert storage.trim() == (0, 0)
    assert all(f.exists() for f in files)
    assert s3.calls == []  # days at or after the cutoff are never even listed


def test_trim_uses_separate_windows_and_removes_empty_days(tmp_path, s3):
    book = put(tmp_path, f"raw/kalshi_ws/KXBTC15M/{day(storage.KEEP_BOOK_DAYS + 5)}/03.jsonl.zst")
    spot_old = put(tmp_path, f"raw/spot/coinbase/{day(storage.KEEP_SPOT_DAYS + 1)}/03.jsonl.zst")
    spot_kept = put(tmp_path, f"raw/spot/coinbase/{day(storage.KEEP_BOOK_DAYS + 5)}/03.jsonl.zst")
    for f in (book, spot_old, spot_kept):
        s3[f.relative_to(tmp_path).as_posix()] = f.stat().st_size

    freed, held = storage.trim()

    assert (freed, held) == (20, 0)
    assert not book.parent.exists() and not spot_old.parent.exists()
    assert book.parent.parent.is_dir()  # series folder stays
    assert spot_kept.exists()


def test_trim_dry_run_deletes_nothing(tmp_path, s3):
    old = day(storage.KEEP_BOOK_DAYS + 1)
    synced = put(tmp_path, f"raw/kalshi_ws/KXETH15M/{old}/00.jsonl.zst")
    unsynced = put(tmp_path, f"raw/kalshi_ws/KXETH15M/{old}/01.jsonl.zst")
    s3[synced.relative_to(tmp_path).as_posix()] = 10

    assert storage.trim(dry_run=True) == (10, 1)
    assert synced.exists() and unsynced.exists()


def test_trim_dry_run_keeps_fully_synced_day_dir(tmp_path, s3):
    f = put(tmp_path, f"raw/kalshi_ws/KXETH15M/{day(storage.KEEP_BOOK_DAYS + 1)}/00.jsonl.zst")
    s3[f.relative_to(tmp_path).as_posix()] = 10

    assert storage.trim(dry_run=True) == (10, 0)
    assert f.exists()


def write_events(path, times_ns):
    path.parent.mkdir(parents=True, exist_ok=True)
    text = "".join(json.dumps({"t": t, "m": {}}) + "\n" for t in times_ns)
    path.write_bytes(zstandard.ZstdCompressor().compress(text.encode()))
    return path


LOCKBOX = datetime(2026, 8, 20, tzinfo=timezone.utc)
L_NS = int(LOCKBOX.timestamp()) * 10**9


@pytest.mark.parametrize("last_ns, expected", [
    (L_NS - 10**9, True),            # closed before the lockbox start
    (L_NS + 10**9, True),            # settled event at close + 1s is still development data
    (L_NS + 10**9 + 1, False),       # anything after that belongs to the lockbox
    (L_NS + 3600 * 10**9, False),
])
def test_ends_by_boundary(tmp_path, last_ns, expected):
    p = write_events(tmp_path / "backfill/kalshi/KXETH15M/2026-08-20/m.jsonl.zst", [L_NS - 60 * 10**9, last_ns])
    assert storage._ends_by(str(p), LOCKBOX) is expected


def test_ends_by_ignores_non_backfill_and_empty_files(tmp_path):
    raw = write_events(tmp_path / "raw/kalshi_ws/KXETH15M/2026-08-20/00.jsonl.zst", [L_NS - 10**9])
    empty = write_events(tmp_path / "backfill/kalshi/KXETH15M/2026-08-20/empty.jsonl.zst", [])
    assert storage._ends_by(str(raw), LOCKBOX) is False
    assert storage._ends_by(str(empty), LOCKBOX) is False


def test_s3_sizes_splits_on_last_tab(monkeypatch):
    out = "raw/a\tb.jsonl.zst\t42\nraw/c.jsonl.zst\t7\n\nNone\n"
    monkeypatch.setattr(storage, "aws", lambda: "aws")
    monkeypatch.setattr(storage.subprocess, "run",
                        lambda *a, **k: subprocess.CompletedProcess(a, 0, stdout=out, stderr=""))
    assert storage._s3_sizes("raw/") == {"raw/a\tb.jsonl.zst": 42, "raw/c.jsonl.zst": 7}


def test_aws_missing_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(storage.shutil, "which", lambda _: None)
    monkeypatch.setenv("HOME", str(tmp_path))
    with pytest.raises(RuntimeError, match="aws CLI not found"):
        storage.aws()
    fallback = put(tmp_path, ".local/bin/aws")
    assert storage.aws() == str(fallback)
