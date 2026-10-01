"""Strategy folders: strategies/<slug>/ holds one strategy's code, config, notes and results.

  strategy.py    the Strategy class (+ an optional fit() classmethod)
  config.json    name, series, description, hypothesis, params, sizing, budget, status
  NOTES.md       hypothesis, iteration log, learnings, results tables (kept up to date by its agent)
  results.json   every pipeline run, appended automatically by `kalshi-lab validate` (the dashboard reads it)
  research/      optional screening scripts

`kalshi-lab new <slug> --series KXSOL15M [--name ...]` creates one from strategies/_template/.
Folders starting with "_" (e.g. _template, _archive) are not strategies.
"""

import argparse
import fcntl
import hashlib
import json
import shutil
import subprocess
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
STRATEGIES = ROOT / "strategies"
DEFAULT_BUDGET = {"full_tests": 3, "lockbox_runs": 1}
STATUSES = ["developing", "paper", "live", "rejected", "parked"]


def folder_for(spec: str) -> Path | None:
    """'eth-volfav', 'strategies/eth-volfav', 'strategies/eth-volfav/strategy.py[:Cls]' -> the folder, if any."""
    target = spec.split(":")[0]
    for cand in (Path(target), ROOT / target, STRATEGIES / target):
        p = cand if cand.is_dir() else cand.parent
        if (p / "config.json").exists() and p.parent.resolve() == STRATEGIES.resolve():
            return p.resolve()
    return None


def strategy_spec(spec: str) -> str:
    """Normalize a strategy reference to 'path/strategy.py[:Class]' (repo-relative when possible)."""
    folder = folder_for(spec)
    if folder is None:
        return spec
    cls = spec.split(":")[1] if ":" in spec else load_config(folder).get("class", "")
    rel = (folder / "strategy.py").relative_to(ROOT)
    return f"{rel}:{cls}" if cls else str(rel)


def all_folders() -> list[Path]:
    return sorted(p for p in STRATEGIES.iterdir() if p.is_dir() and not p.name.startswith("_")
                  and (p / "config.json").exists())


GRANTS = STRATEGIES / "_budgets.json"  # user-granted extra budget: {"<slug>": {"full_tests": 5}}; agents can't edit it


def budget(folder: Path, c: dict) -> dict:
    """Effective budget. A strategy's own config.json can only LOWER the defaults (its agent can edit it);
    raising them needs an entry in strategies/_budgets.json, which only the user grants."""
    grant = json.loads(GRANTS.read_text()).get(folder.name, {}) if GRANTS.exists() else {}
    own = c.get("budget") or {}
    return {k: grant.get(k, min(int(own.get(k, v)), v)) for k, v in DEFAULT_BUDGET.items()}


def load_config(folder: Path) -> dict:
    c = json.loads((folder / "config.json").read_text())
    c["budget"] = budget(folder, c)
    return c


def save_config(folder: Path, c: dict):
    (folder / "config.json").write_text(json.dumps(c, indent=2) + "\n")


@contextmanager
def _locked(path: Path):
    lock = path.with_suffix(".lock")
    with open(lock, "w") as fh:
        fcntl.flock(fh, fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(fh, fcntl.LOCK_UN)


def load_results(folder: Path) -> dict:
    p = folder / "results.json"
    return json.loads(p.read_text()) if p.exists() else {"runs": []}


def append_result(folder: Path, record: dict):
    p = folder / "results.json"
    with _locked(p):
        r = load_results(folder)
        r["runs"].append(record)
        p.write_text(json.dumps(r, indent=1) + "\n")


# ---------------------------------------------------------------- the ledger (authoritative)
# results.json lives in the strategy's folder, where its agent can edit it, so it is only a display copy.
# The pipeline also appends every run to results/_ledger/<slug>.jsonl as a hash chain; budgets and the
# lockbox gate read only the ledger, and the dashboard flags any results.json that disagrees with it.
LEDGER = ROOT / "results" / "_ledger"


CODE_V = 2  # fingerprint version recorded in the ledger as code_v


def code_hash(folder: Path, legacy: bool = False) -> str:
    """Fingerprint of a strategy's code: every .py/.json file in its folder except research/, results.json,
    config.json and params/. params/ holds fit() output, which every test rewrites; the lockbox and audits set it
    aside and refit, so fitted values always come from the code. (legacy=True: the v1 fingerprint, which
    included params/, for comparing with ledger entries recorded before code_v existed.)"""
    h = hashlib.sha256()
    for f in sorted(folder.rglob("*")):
        rel = f.relative_to(folder).parts
        if f.is_file() and f.suffix in (".py", ".json") and "research" not in f.parts and "__pycache__" not in f.parts \
                and f.name not in ("results.json", "config.json") and (legacy or rel[0] != "params") \
                and not rel[0].startswith(".params-held"):
            h.update(str(f.relative_to(folder)).encode())
            h.update(f.read_bytes())
    return h.hexdigest()[:16]


def _digest(rec: dict) -> str:
    body = {k: v for k, v in rec.items() if k != "hash"}
    return hashlib.sha256(json.dumps(body, sort_keys=True, default=str).encode()).hexdigest()


def ledger_runs(slug: str) -> list[dict]:
    p = LEDGER / f"{slug}.jsonl"
    return [json.loads(line) for line in p.read_text().splitlines() if line.strip()] if p.exists() else []


def ledger_ok(slug: str) -> bool:
    """True if the hash chain is intact."""
    prev = ""
    for rec in ledger_runs(slug):
        if rec.get("prev") != prev or rec.get("hash") != _digest(rec):
            return False
        prev = rec["hash"]
    return True


def ledger_append(slug: str, rec: dict) -> dict:
    LEDGER.mkdir(parents=True, exist_ok=True)
    p = LEDGER / f"{slug}.jsonl"
    with _locked(p):
        runs = ledger_runs(slug)
        rec = {**rec, "prev": runs[-1]["hash"] if runs else ""}
        rec["hash"] = _digest(rec)
        with open(p, "a") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
    return rec


def results_match_ledger(folder: Path) -> bool:
    """Does the folder's results.json agree with the ledger (same jobs, verdicts and headline numbers)?"""
    key = lambda r: (r.get("stage"), r.get("job"), r.get("verdict"), json.dumps((r.get("cards") or {}).get("POOLED"), sort_keys=True))
    shown = [key(r) for r in load_results(folder)["runs"] if not r.get("pre_lockbox_rules")]
    real = [key(r) for r in ledger_runs(folder.name)]
    return shown == real


def count_runs(folder: Path, stage: str) -> int:
    """Budget accounting, from the ledger (not the editable results.json)."""
    return sum(1 for r in ledger_runs(folder.name) if r.get("stage") == stage and not r.get("crashed"))


def git_rev() -> str:
    try:
        rev = subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
        dirty = subprocess.call(["git", "diff", "--quiet"], cwd=ROOT) != 0
        return rev + ("+dirty" if dirty else "")
    except Exception:
        return "unknown"


def new(argv=None):
    ap = argparse.ArgumentParser(prog="kalshi-lab new", description="create strategies/<slug>/ from the template")
    ap.add_argument("slug", help="short kebab-case name, e.g. sol-jump-fade")
    ap.add_argument("--series", nargs="+", required=True)
    ap.add_argument("--name", help="display name")
    a = ap.parse_args(argv)
    dst = STRATEGIES / a.slug
    if dst.exists():
        raise SystemExit(f"{dst} already exists")
    shutil.copytree(STRATEGIES / "_template", dst, ignore=shutil.ignore_patterns("__pycache__"))
    c = load_config(dst)
    c.update(slug=a.slug, name=a.name or a.slug.replace("-", " ").title(), series=a.series,
             created=datetime.now(timezone.utc).date().isoformat())
    save_config(dst, c)
    notes = (dst / "NOTES.md").read_text().replace("{{name}}", c["name"]).replace("{{series}}", ", ".join(a.series))
    (dst / "NOTES.md").write_text(notes)
    print(f"created {dst.relative_to(ROOT)}/ - edit strategy.py, config.json (description, hypothesis) and NOTES.md")
