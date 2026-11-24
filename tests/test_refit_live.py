import json
import runpy
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

SLUG = "xrp-volfav-early"


@pytest.fixture
def refit(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "research/refit_live.py"
    main = runpy.run_path(str(script))["main"]
    clock = SimpleNamespace(now=datetime(2026, 11, 7, 14, tzinfo=timezone.utc))
    monkeypatch.setitem(main.__globals__, "datetime",
                        SimpleNamespace(now=lambda tz: clock.now, fromisoformat=datetime.fromisoformat))
    monkeypatch.setitem(main.__globals__, "DATA", tmp_path)
    checkpoint = tmp_path / "logs" / "nightly-backfill-through"
    checkpoint.parent.mkdir()
    checkpoint.write_text(clock.now.isoformat())
    monkeypatch.setitem(main.__globals__, "_current", lambda *args: None)
    monkeypatch.setitem(main.__globals__, "aws", lambda: "aws")
    upload = Mock()
    monkeypatch.setitem(main.__globals__, "subprocess", SimpleNamespace(check_call=upload))
    model = {"beta": [0, 0.2, 0.2, 0.2], "ratio_threshold": 1.5, "n_markets": 100}
    vol_fit = SimpleNamespace()

    def fit(series, until, pct):
        (vol_fit.PARAMS / "candidate.json").write_text(json.dumps(model))
        return "candidate.json"

    vol_fit.fit_model = Mock(side_effect=fit)
    monkeypatch.setitem(main.__globals__, "_vol_fit", lambda slug: vol_fit)
    return SimpleNamespace(run=lambda *args: main(["--slug", SLUG, *args]), upload=upload,
                           fit=vol_fit.fit_model, clock=clock, model=model, checkpoint=checkpoint,
                           marker=tmp_path / "models" / SLUG / "_refit_month")


def test_refit_catches_up_after_first_at_month_boundary_once(refit):
    assert refit.run() == 0
    assert refit.fit.call_args.args == ("KXXRP15M", "2026-11-01T00:00")
    assert refit.marker.read_text().strip() == "2026-11"
    assert refit.upload.call_count == 2
    assert refit.run() == 0
    assert refit.fit.call_count == 1
    refit.clock.now = datetime(2026, 12, 3, tzinfo=timezone.utc)
    refit.checkpoint.write_text(refit.clock.now.isoformat())
    assert refit.run() == 0
    assert refit.fit.call_args.args == ("KXXRP15M", "2026-12-01T00:00")


@pytest.mark.parametrize("coverage", [None, "2026-10-31T23:45:00+00:00"])
def test_refit_waits_for_backfill_to_cover_month_start(refit, coverage):
    refit.clock.now = datetime(2026, 11, 1, 0, 10, tzinfo=timezone.utc)
    if coverage is None:
        refit.checkpoint.unlink()
    else:
        refit.checkpoint.write_text(coverage)
    assert refit.run() == 0
    assert not refit.fit.called
    assert not refit.upload.called
    assert not refit.marker.exists()

    refit.checkpoint.write_text("2026-11-01T00:00:00+00:00")
    assert refit.run() == 0
    assert refit.fit.call_args.args == ("KXXRP15M", "2026-11-01T00:00")
    assert refit.marker.read_text().strip() == "2026-11"


def test_refit_dry_run_and_failed_upload_do_not_mark_month(refit):
    assert refit.run("--dry-run") == 0
    assert not refit.upload.called
    assert not refit.marker.exists()
    refit.upload.side_effect = [None, subprocess.CalledProcessError(1, "aws")]
    with pytest.raises(subprocess.CalledProcessError):
        refit.run()
    assert not refit.marker.exists()
    refit.upload.side_effect = None
    assert refit.run() == 0
    assert refit.marker.read_text().strip() == "2026-11"
    assert refit.run("--force") == 0
    assert refit.fit.call_args.args == ("KXXRP15M", "2026-11-07T00:00")


@pytest.mark.parametrize("coverage", [None, "2026-10-31T23:45:00+00:00"])
@pytest.mark.parametrize(("flag", "day", "uploads"), [("--force", "07", 2), ("--dry-run", "01", 0)])
def test_manual_refit_ignores_nightly_checkpoint(refit, coverage, flag, day, uploads):
    if coverage is None:
        refit.checkpoint.unlink()
    else:
        refit.checkpoint.write_text(coverage)

    assert refit.run(flag) == 0
    assert refit.fit.call_args.args == ("KXXRP15M", f"2026-11-{day}T00:00")
    assert refit.upload.call_count == uploads
    assert not refit.marker.exists()


def test_refit_rejection_keeps_old_model_and_does_not_repeat_daily(refit):
    refit.model["ratio_threshold"] = 4
    assert refit.run() == 1
    assert refit.marker.read_text().strip() == "2026-11"
    assert refit.upload.call_count == 1
    assert refit.upload.call_args.args[0][-1].endswith("/refit_20261107.json")
    assert refit.run() == 0
    assert refit.fit.call_count == 1
