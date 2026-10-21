"""Monthly refit of the vol models that live/paper VolFavorite traders use (research server, nightly service).

The walk-forward that validated VolFavorite refits its model before every month on all earlier data; this does the
same for the traders. On the 1st of each month (UTC), or with --force, for each strategy in REFIT:
  1. fit the strategy's own vol_fit.fit_model on every market closing before today 00:00 UTC (expanding window),
  2. sanity-check it against the model the traders use now (repo params/ or the last refit),
  3. if it passes, upload model + report to s3://<bucket>/models/<slug>/; the trading server pulls that hourly
     (`kalshi-lab models-pull`) into ~/kalshi-data/models/<slug>/, and the strategy re-reads it without a restart.
A failed check uploads only the report (the traders keep the previous model) and exits non-zero.

  python research/refit_live.py [--force] [--dry-run] [--slug eth-volfav2 ...]
"""

import argparse
import importlib.util
import json
import math
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))
from kalshi_lab.storage import BUCKET, DATA, aws  # noqa: E402

REFIT = {"eth-volfav2": "KXETH15M", "xrp-volfav": "KXXRP15M", "eth-volfav-kelly": "KXETH15M"}  # slug -> series (the strategies trading these models)
MAX_THR_CHANGE = 0.20  # relative change in the entry threshold beyond which a human should look first


def _vol_fit(slug: str):
    spec = importlib.util.spec_from_file_location(f"vol_fit_{slug.replace('-', '_')}",
                                                  ROOT / "strategies" / slug / "vol_fit.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _current(slug: str, series: str) -> dict | None:
    """The model the traders use now: the last refit in S3, else the repo's params file."""
    name = f"vol_model_{series}.json"
    with tempfile.TemporaryDirectory() as td:
        if subprocess.call([aws(), "s3", "cp", "--only-show-errors", f"s3://{BUCKET}/models/{slug}/{name}", td],
                           stderr=subprocess.DEVNULL) == 0 and (Path(td) / name).exists():
            return json.loads((Path(td) / name).read_text())
    p = ROOT / "strategies" / slug / "params" / name
    return json.loads(p.read_text()) if p.exists() else None


def check(new: dict, old: dict | None) -> list[str]:
    problems = []
    b = new["beta"]
    if not all(math.isfinite(x) for x in b) or not any(b):
        problems.append("betas not finite or all zero")
    rv = sum(b[1:4])
    if not 0.3 < rv < 1.5:
        problems.append(f"rv betas sum {rv:.2f} outside 0.3..1.5")
    if not 1.0 < new["ratio_threshold"] < 3.0:
        problems.append(f"threshold {new['ratio_threshold']:.3f} outside 1..3")
    if old:
        if new["n_markets"] < old.get("n_markets", 0):
            problems.append(f"fewer markets than the current model ({new['n_markets']} < {old['n_markets']})")
        ch = new["ratio_threshold"] / old["ratio_threshold"] - 1
        if abs(ch) > MAX_THR_CHANGE:
            problems.append(f"threshold moved {ch:+.0%} ({old['ratio_threshold']:.3f} -> {new['ratio_threshold']:.3f})")
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--force", action="store_true", help="refit now, not only on the 1st")
    ap.add_argument("--dry-run", action="store_true", help="fit and check, upload nothing")
    ap.add_argument("--slug", nargs="+", default=list(REFIT))
    a = ap.parse_args(argv)
    now = datetime.now(timezone.utc)
    if now.day != 1 and not a.force:
        print(f"{now:%F %T} refit_live: not the 1st, nothing to do")
        return 0
    until = now.strftime("%Y-%m-%dT00:00")
    failed = False
    for slug in a.slug:
        series = REFIT[slug]
        vf = _vol_fit(slug)
        out = DATA / "models" / slug
        out.mkdir(parents=True, exist_ok=True)
        vf.PARAMS = out  # write the fit here, not into the strategy folder
        fitted = vf.fit_model(series, until, pct=0.7)
        new = json.loads((out / fitted).read_text())
        old = _current(slug, series)
        problems = check(new, old)
        name = f"vol_model_{series}.json"
        report = dict(slug=slug, series=series, fitted_at=now.isoformat(), fit_until=until, ok=not problems,
                      problems=problems, n_markets=new["n_markets"], threshold=new["ratio_threshold"],
                      rv_betas=new["beta"][1:4], previous=dict(fit_until=old.get("fit_until"),
                                                                 n_markets=old.get("n_markets"),
                                                                 threshold=old.get("ratio_threshold")) if old else None)
        (out / f"refit_{now:%Y%m%d}.json").write_text(json.dumps(report, indent=1))
        print(json.dumps(report))
        if a.dry_run:
            continue
        files = [out / f"refit_{now:%Y%m%d}.json"]
        if problems:
            failed = True
        else:
            (out / name).write_text((out / fitted).read_text())
            files.append(out / name)
        for f in files:
            subprocess.check_call([aws(), "s3", "cp", "--only-show-errors", str(f), f"s3://{BUCKET}/models/{slug}/{f.name}"])
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
