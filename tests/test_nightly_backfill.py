import runpy
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from kalshi_lab.data import backfill


@pytest.mark.parametrize(("previous", "legacy", "start"), [
    ("2026-11-01T00:30:00+00:00", False, "2026-10-29T00:30:00+00:00"),
    (None, True, "2026-10-29T00:30:00+00:00"),
    (None, False, "2026-11-06T14:00:00+00:00"),
])
def test_nightly_backfill_window(tmp_path, monkeypatch, previous, legacy, start):
    main, checkpoint, run = nightly(tmp_path, monkeypatch)
    if previous:
        checkpoint.write_text(previous)
    if legacy:
        uploaded = datetime(2026, 11, 1, 0, 30, tzinfo=timezone.utc).astimezone()
        (tmp_path / "logs" / "nightly.log").write_text(
            f"{uploaded:%F %T} uploaded in 15s\n"
            "2026-11-02 00:30:00 uploaded in 15s WITH ERRORS (rc=1); not trimming\n")

    main()

    download, upload = (call.args[0] for call in run.call_args_list)
    assert download[3] == "backfill"
    assert download[download.index("--start") + 1] == start
    assert download[download.index("--end") + 1] == "2026-11-09T14:00:00+00:00"
    assert "--strict" in download
    assert upload[3:] == ["s3-push", "--dirs", "backfill", "--no-trim"]
    assert checkpoint.read_text().strip() == "2026-11-09T14:00:00+00:00"


@pytest.mark.parametrize("command", ["backfill", "s3-push"])
def test_nightly_backfill_failure_does_not_advance(tmp_path, monkeypatch, command):
    main, checkpoint, run = nightly(tmp_path, monkeypatch)
    previous = "2026-11-01T00:30:00+00:00"
    checkpoint.write_text(previous)

    def fail(argv):
        if argv[3] == command:
            raise subprocess.CalledProcessError(1, argv)

    run.side_effect = fail
    with pytest.raises(subprocess.CalledProcessError):
        main()
    assert checkpoint.read_text() == previous


def nightly(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "deploy/research/nightly-backfill.py"
    main = runpy.run_path(str(script))["main"]
    now = datetime(2026, 11, 9, 14, tzinfo=timezone.utc)
    monkeypatch.setitem(main.__globals__, "datetime", type("Clock", (datetime,), {"now": lambda tz: now}))
    monkeypatch.setitem(main.__globals__, "DATA", tmp_path)
    run = Mock()
    monkeypatch.setitem(main.__globals__, "subprocess", Mock(check_call=run))
    logs = tmp_path / "logs"
    logs.mkdir()
    return main, logs / "nightly-backfill-through", run


def test_strict_market_backfill_propagates_failed_trade_download(tmp_path, monkeypatch):
    cutoff = "2026-11-01T00:00:00+00:00"
    market = {"close_time": cutoff, "ticker": "TEST", "result": "yes"}
    monkeypatch.setattr(backfill, "settled_markets", lambda *args: [(market, False)])
    rest = Mock()
    rest.get.return_value = {"trades_created_ts": cutoff}
    rest.paginate.side_effect = RuntimeError("trade download failed")
    now = datetime.now(timezone.utc)
    with pytest.raises(RuntimeError, match="trade download failed"):
        backfill.backfill_kalshi(rest, tmp_path, "TEST", now, now, strict=True)
    backfill.backfill_kalshi(rest, tmp_path, "TEST", now, now)
