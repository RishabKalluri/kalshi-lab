"""Staged strategy validation: smoke -> quick -> full, with a report card.

    kalshi-lab test strategies/my_idea.py --series KXETH15M [-p key=val ...]

runs `smoke` on the server in the foreground (~1 min) and, if it passes, queues `quick` and `full` on
the server's background worker (see jobs.py). Results appear in the dashboard's Jobs panel.

Stages (each is one or more ordinary backtests):
  smoke  recorded books, last 2 hours (or 6h of backfill): it runs, trades, isn't rejected by risk limits
  quick  backfill, last 3 days + recorded books, last 6 hours   (~5-10 min on the server). Gate: a clearly
         negative quick (all runs lose, a CI entirely below zero) stops the job before the full test.
  lockbox  ONE SHOT on data from LOCKBOX_START on (never used by smoke/quick/full), only after a promising
           full test: pass if profitable, strong pass if the 95% CI is above 0. Fail = reject the idea.
  full   WALK-FORWARD over all backfilled months before the lockbox: one backtest per month. If the strategy defines
         fit(series, until), it's refit before each month on data before that month only, so every
         month is out of sample. + the last 3 months again at 2x latency + all recorded books.
         Months run in parallel (KALSHI_TEST_WORKERS, default: CPU cores - 2).

Report card: per run, PnL, contracts, PnL/contract, a 95% CI on PnL/contract from a bootstrap over
markets (markets are the independent unit; fills within a market are not), days positive, t-stat,
plus a POOLED row across all walk-forward months.
Verdict: promising = pooled CI above 0, >= 60% of months positive, and still positive at 2x latency;
         reject = pooled CI entirely below 0 or < 40% of months positive; otherwise inconclusive.
Decisions use these engine results only; research scripts are for screening ideas.
"""

import json
import os
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
RESULTS = ROOT / "results"
DATA = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser()
BACKFILL = DATA.parent / "backfill"
UTC = timezone.utc


def backfill_days(series: list[str]) -> list[str]:
    sets = [{p.name for p in (BACKFILL / "kalshi" / s).glob("*") if p.is_dir()} for s in series]
    return sorted(set.intersection(*sets)) if sets and all(sets) else []


def recorded_range(series: list[str]) -> tuple[datetime, datetime] | None:
    files = sorted(f for s in series for f in (DATA / "kalshi_ws" / s).glob("*/*.jsonl.zst"))
    if not files:
        return None
    first, last = files[0], files[-1]
    f = lambda p: datetime.strptime(f"{p.parent.name} {p.name[:2]}", "%Y-%m-%d %H").replace(tzinfo=UTC)
    return f(first), min(datetime.now(UTC) - timedelta(minutes=20), f(last) + timedelta(hours=1))


# The lockbox: data on/after this date is never used by smoke/quick/full. A strategy sees it exactly once,
# in the `lockbox` stage, after its full test is promising. Move it forward only deliberately (it's global).
LOCKBOX_START = datetime.fromisoformat(os.environ.get("KALSHI_LOCKBOX_START", "2026-08-20")).replace(tzinfo=UTC)


def _unseal_token() -> str:
    """A per-machine secret outside the repo; backtests touching lockbox dates require it (set by the lockbox stage)."""
    import secrets
    p = Path("~/.kalshi/lockbox.token").expanduser()
    if not p.exists():
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(secrets.token_hex(16))
        p.chmod(0o600)
    return p.read_text().strip()


def lockbox_guard(start: datetime, end: datetime):
    """Refuse backtests that reach into the lockbox unless the lockbox stage launched them."""
    if end > LOCKBOX_START and os.environ.get("KALSHI_LOCKBOX_UNSEAL") != _unseal_token():
        raise SystemExit(f"LOCKBOX: this backtest ends {end:%Y-%m-%d}, after the lockbox start {LOCKBOX_START:%Y-%m-%d}. "
                         "Only `kalshi-lab test <slug> --stages lockbox` may use that data. Use earlier dates.")


def _months(first: datetime, last: datetime) -> list[tuple[datetime, datetime]]:
    out, m = [], first.replace(day=1)
    while m < last:
        nxt = (m + timedelta(days=32)).replace(day=1)
        s0, e0 = max(m, first), min(nxt, last)
        if (e0 - s0) >= timedelta(days=5):  # skip slivers
            out.append((s0, e0))
        m = nxt
    return out


def plan(stage: str, series: list[str], fits: bool = False, min_train: int = 2) -> list[dict]:
    """The backtest runs (name + source + window + overrides) that make up a stage."""
    rec = recorded_range(series)
    days = backfill_days(series)
    runs = []
    if not days:
        return runs
    first = datetime.fromisoformat(days[0]).replace(tzinfo=UTC)
    data_end = datetime.fromisoformat(days[-1]).replace(tzinfo=UTC) + timedelta(days=1)
    dev_end = min(LOCKBOX_START, data_end)  # everything before the lockbox
    if stage == "smoke":
        # Mechanics only: the last 6 hours of development data (long enough for ~1h warm-ups).
        runs.append(dict(name="smoke", source="backfill", start=dev_end - timedelta(hours=6), end=dev_end,
                         fit_until=dev_end - timedelta(hours=6)))
    elif stage == "quick":
        runs.append(dict(name="quick-backfill", source="backfill", start=dev_end - timedelta(days=3), end=dev_end,
                         fit_until=dev_end - timedelta(days=3)))
    elif stage == "full":
        months = _months(first, dev_end)
        train_months = min_train if fits else 0
        for s0, e0 in months[train_months:]:
            runs.append(dict(name=f"wf-{s0:%Y-%m}", source="backfill", start=s0, end=e0, fit_until=s0))
        for s0, e0 in months[train_months:][-3:]:
            runs.append(dict(name=f"lat2x-{s0:%Y-%m}", source="backfill", start=s0, end=e0, fit_until=s0,
                             latency_ms=300))
    elif stage == "lockbox":
        # One shot at data the strategy has never seen, fit only on data before the lockbox.
        if data_end > LOCKBOX_START:
            for s0, e0 in _months(LOCKBOX_START, data_end):
                runs.append(dict(name=f"lockbox-{s0:%Y-%m}", source="backfill", start=s0, end=e0, fit_until=LOCKBOX_START))
        if rec and rec[1] > LOCKBOX_START:
            runs.append(dict(name="lockbox-recorded", source="recorded", start=max(rec[0], LOCKBOX_START), end=rec[1],
                             fit_until=LOCKBOX_START))
    else:
        raise ValueError(stage)
    return runs


def run_backtest(strategy: str, series: list[str], params: list[str], r: dict, out: Path, log, i=1, n=1) -> dict | None:
    params = list(params) + [f"{k}={v}" for k, v in r.get("params", {}).items()]
    env = dict(os.environ)
    if r["name"].startswith("lockbox"):
        env["KALSHI_LOCKBOX_UNSEAL"] = _unseal_token()  # the only way a backtest may touch lockbox dates
    cmd = [sys.executable, "-m", "kalshi_lab", "backtest", strategy, "--series", *series, "--source", r["source"],
           "--start", r["start"].isoformat(), "--end", r["end"].isoformat(), "--out", str(out),
           "--latency-ms", str(r.get("latency_ms", 150)), "--workers", "1"]
    for p in params:
        cmd += ["-p", p]
    log(f"  [{i}/{n}] {datetime.now(UTC):%Y-%m-%dT%H:%M:%S} running {r['name']}: {r['source']} "
        f"{r['start']:%m-%d %H:%M} -> {r['end']:%m-%d %H:%M}")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, env=env)
    if proc.returncode != 0:
        log(f"  FAILED {r['name']}:\n" + (proc.stderr or proc.stdout)[-3000:])
        return None
    return json.loads((out / "summary.json").read_text())


def card(run_dir: Path, n_boot: int = 2000) -> dict:
    """Report-card metrics for one run directory."""
    s = json.loads((run_dir / "summary.json").read_text())
    m = pd.read_csv(run_dir / "markets.csv", parse_dates=["settle_time"])
    t = m[m.fills > 0]
    out = dict(pnl=s["pnl"], contracts=s["contracts"], markets=int(len(t)), fees=s["fees"],
               pnl_per_contract_c=round(100 * s["pnl"] / s["contracts"], 3) if s["contracts"] else None,
               t_stat=s.get("t_stat"), max_drawdown=s.get("max_drawdown"), rejects=s.get("rejects"))
    if len(t) >= 5 and t.volume.sum() > 0:
        rng = np.random.default_rng(0)
        idx = rng.integers(0, len(t), size=(n_boot, len(t)))
        pnl, vol = t.pnl.to_numpy()[idx].sum(1), t.volume.to_numpy()[idx].sum(1)
        lo, hi = np.percentile(100 * pnl / vol, [2.5, 97.5])
        out["ci95_c"] = [round(float(lo), 3), round(float(hi), 3)]
        daily = t.groupby(t.settle_time.dt.date).pnl.sum()
        out["days_positive"] = f"{int((daily > 0).sum())}/{len(daily)}"
    return out


def pooled_card(run_dirs: list[Path], n_boot: int = 2000) -> dict | None:
    """Report-card metrics across several runs (e.g. all walk-forward months), bootstrapped over markets."""
    ms = []
    for d in run_dirs:
        if (d / "markets.csv").exists():
            m = pd.read_csv(d / "markets.csv", parse_dates=["settle_time"])
            ms.append(m[m.fills > 0])
    if not ms:
        return None
    t = pd.concat(ms)
    out = dict(pnl=round(float(t.pnl.sum()), 2), contracts=float(t.volume.sum()), markets=int(len(t)),
               pnl_per_contract_c=round(100 * t.pnl.sum() / t.volume.sum(), 3) if t.volume.sum() else None)
    if len(t) >= 5:
        rng = np.random.default_rng(0)
        idx = rng.integers(0, len(t), size=(n_boot, len(t)))
        lo, hi = np.percentile(100 * t.pnl.to_numpy()[idx].sum(1) / t.volume.to_numpy()[idx].sum(1), [2.5, 97.5])
        out["ci95_c"] = [round(float(lo), 3), round(float(hi), 3)]
        daily = t.groupby(t.settle_time.dt.date).pnl.sum()
        out["days_positive"] = f"{int((daily > 0).sum())}/{len(daily)}"
        eq = t.sort_values("settle_time").pnl.cumsum()
        out["max_drawdown"] = round(float((eq.cummax() - eq).max()), 2)
    return out


def verdict(cards: dict) -> str:
    wf = {k: c for k, c in cards.items() if k.startswith("wf-") and c}
    pooled, lat = cards.get("POOLED"), cards.get("POOLED-lat2x")
    if not wf or not pooled or not pooled.get("ci95_c"):
        return "incomplete"
    frac = sum(c["pnl"] > 0 for c in wf.values()) / len(wf)
    if pooled["ci95_c"][1] < 0 or frac < 0.4:
        return "reject"
    if pooled["ci95_c"][0] > 0 and frac >= 0.6 and lat and lat["pnl"] > 0:
        return "promising"
    return "inconclusive"


def quick_gate(cards: dict) -> str | None:
    """Stop before the full test when quick is clearly negative: every run loses money and at least one
    has its whole 95% CI below zero. Merely unclear results go on to the full test."""
    runs = [c for c in cards.values() if c and c.get("contracts")]
    if not runs:
        return "no trades in the quick stage"
    if all(c["pnl"] < 0 for c in runs) and any(c.get("ci95_c") and c["ci95_c"][1] < 0 for c in runs):
        return "clearly negative: every quick run lost money and at least one 95% CI is entirely below zero"
    return None


def format_cards(cards: dict) -> str:
    cols = ["pnl", "contracts", "markets", "pnl_per_contract_c", "ci95_c", "days_positive", "t_stat", "max_drawdown"]
    lines = [f"{'run':<18}" + "".join(f"{c:>20}" for c in cols)]
    for name, c in cards.items():
        if c:
            lines.append(f"{name:<18}" + "".join(f"{str(c.get(k, '')):>20}" for k in cols))
    return "\n".join(lines)


def smoke_checks(summary: dict) -> list[str]:
    problems = []
    if summary["fills"] == 0:
        problems.append("no fills in the smoke window (strategy may never trade, or the window is too short)")
    orders = summary["fills"] + summary.get("rejects", 0)
    if summary.get("rejects", 0) > max(5, 0.5 * orders):
        problems.append(f"{summary['rejects']} orders rejected by risk limits: {summary.get('reject_reasons')}")
    return problems


def lockbox_verdict(cards: dict) -> str:
    """One shot, so no tuning: pass if the never-seen data is profitable; strong pass if its 95% CI is above 0."""
    pooled = cards.get("POOLED")
    if not pooled or not pooled.get("contracts"):
        return "incomplete"
    if pooled["pnl"] <= 0:
        return "fail"
    return "strong pass" if pooled.get("ci95_c") and pooled["ci95_c"][0] > 0 else "pass"


def _hold_params(folder: Path, job: str, log):
    """Lockbox/audit: move the strategy's params/ aside so every fitted file comes from fit() on this code (a file
    hand-tuned after the full test can't reach the lockbox). Restored on exit, the held files winning."""
    import atexit
    import shutil
    import signal
    src = folder / "params"
    if not src.exists():
        return
    held = folder / f".params-held-{job}"
    src.rename(held)
    log(f"  params/ set aside for this run ({len(list(held.iterdir()))} files); fit() regenerates what it needs")

    def restore():
        if not held.exists():
            return
        src.mkdir(exist_ok=True)
        for f in held.iterdir():
            shutil.move(str(f), str(src / f.name))
        held.rmdir()
    atexit.register(restore)
    signal.signal(signal.SIGTERM, lambda *_: sys.exit(143))  # so a cancel still restores params/


def main(argv=None):
    """`kalshi-lab validate smoke|quick|full|lockbox <strategy folder or file> [--series ...] [-p ...] [--job ID]`."""
    import argparse

    from .strategy_dir import (CODE_V, append_result, code_hash, count_runs, folder_for, git_rev, ledger_append,
                               ledger_ok, ledger_runs, load_config, strategy_spec)
    ap = argparse.ArgumentParser(prog="kalshi-lab validate")
    ap.add_argument("stage", choices=["smoke", "quick", "full", "lockbox"])
    ap.add_argument("strategy", help="strategy folder/slug (strategies/<slug>) or a .py file")
    ap.add_argument("--series", nargs="+", help="default: the folder's config.json")
    ap.add_argument("-p", "--param", action="append", default=[])
    ap.add_argument("--job", default=None, help="job id (names the result dirs)")
    ap.add_argument("--force", action="store_true", help="override the full-test budget / one-shot lockbox (user only)")
    ap.add_argument("--note", default="", help="what changed in this iteration (logged to results.json)")
    ap.add_argument("--audit", action="store_true", help="re-run without recording; compare to the ledger (kalshi-lab audit)")
    a = ap.parse_args(argv)
    log = lambda s: print(s, flush=True)
    folder = folder_for(a.strategy)
    cfg = load_config(folder) if folder else {}
    series = a.series or cfg.get("series") or ["KXBTC15M"]
    params = list(cfg.get("params", [])) + a.param  # folder defaults, then explicit overrides
    spec = strategy_spec(a.strategy)
    slug = folder.name if folder else Path(spec.split(":")[0]).stem
    job = a.job or f"{slug}-{datetime.now():%m%d-%H%M%S}"

    if folder and not ledger_ok(folder.name):
        log(f"LEDGER: results/_ledger/{folder.name}.jsonl fails its hash check (edited?). Tell the user; nothing runs.")
        sys.exit(6)
    if folder and not a.force and not a.audit:  # anti-overfitting guards (all read the ledger, not results.json)
        budget = cfg["budget"]
        if a.stage == "full" and count_runs(folder, "full") >= budget.get("full_tests", 3):
            log(f"BUDGET: {slug} has used its {budget['full_tests']} full tests. Log what you learned and stop, "
                f"or ask the user for more (validate --force).")
            sys.exit(5)
        if a.stage == "lockbox" and count_runs(folder, "lockbox") >= budget.get("lockbox_runs", 1):
            log(f"LOCKBOX: {slug} already used its lockbox. It is one-shot; a failed lockbox means the idea is rejected.")
            sys.exit(5)
        if a.stage == "lockbox":
            last_full = next((r for r in reversed(ledger_runs(folder.name)) if r.get("stage") == "full"), None)
            if not last_full or last_full.get("verdict") != "promising":
                log("LOCKBOX: only after a promising full test.")
                sys.exit(5)
            if last_full.get("code") != code_hash(folder, legacy=last_full.get("code_v") != CODE_V):
                log("LOCKBOX: the code changed since the promising full test. Rerun the full test on this exact code first.")
                sys.exit(5)

    legacy_code = code_hash(folder, legacy=True) if folder else None
    if folder and (a.stage == "lockbox" or a.audit):
        _hold_params(folder, job, log)

    from .backtest import load_strategy
    cls = load_strategy(spec)
    fits = callable(getattr(cls, "fit", None))
    runs = plan(a.stage, series, fits=fits)
    if not runs:
        log(f"no data for {series} to run the {a.stage} stage")
        sys.exit(2)
    user_keys = {p.split("=", 1)[0] for p in params}
    if fits:  # refit on data before each window; explicit params win
        cache = {}
        for r in runs:
            until = r.get("fit_until")
            key = until.isoformat() if until else None
            if key not in cache:
                log(f"  fit: data before {key or 'now'}")
                cache[key] = cls.fit(series, key)
            r["params"] = {k: v for k, v in cache[key].items() if k not in user_keys}
    cards = {}
    workers = int(os.environ.get("KALSHI_TEST_WORKERS", max(1, (os.cpu_count() or 2) - 2)))
    log(f"plan: {len(runs)} runs, {workers} at a time (lockbox starts {LOCKBOX_START:%Y-%m-%d})")
    started = datetime.now(UTC).isoformat()

    def one(i_r):
        i, r = i_r
        out = RESULTS / f"{job}-{r['name']}"
        return r["name"], out, run_backtest(spec, series, params, r, out, log, i, len(runs))

    code = code_hash(folder) if folder else None

    def record(verdict_, gate=None, crashed=False):
        if a.audit:
            audit_compare(folder, a.stage, code, legacy_code, cards, verdict_, log)
            return
        if not folder:
            return
        windows = {r["name"]: [r["start"].isoformat(), r["end"].isoformat()] for r in runs}
        rec = dict(stage=a.stage, job=job, started=started, finished=datetime.now(UTC).isoformat(), git=git_rev(),
                   code=code, code_v=CODE_V, params=params, note=a.note, iteration=count_runs(folder, "full") + 1, windows=windows,
                   cards=cards, verdict=verdict_, gate=gate, crashed=crashed, lockbox_start=LOCKBOX_START.isoformat())
        rec = ledger_append(folder.name, rec)  # authoritative
        append_result(folder, rec)              # display copy for the dashboard

    with ThreadPoolExecutor(max_workers=1 if a.stage == "smoke" else workers) as pool:
        results = list(pool.map(one, enumerate(runs, 1)))
    for name, out, s in results:
        if s is None:
            record("crashed", crashed=True)
            sys.exit(1)
        cards[name] = card(out)
    if a.stage == "smoke":
        problems = smoke_checks(results[0][2])
        log(format_cards(cards))
        if problems:
            log("SMOKE FAILED:\n  - " + "\n  - ".join(problems))
            record("failed", gate="; ".join(problems))
            sys.exit(3)
        log("smoke passed")
        record("passed")
        return
    if a.stage in ("full", "lockbox"):
        main_dirs = [out for name, out, _ in results
                     if (name.startswith("wf-") if a.stage == "full" else name.startswith("lockbox-") and name != "lockbox-recorded")]
        cards["POOLED"] = pooled_card(main_dirs)
        lat_dirs = [out for name, out, _ in results if name.startswith("lat2x-")]
        if lat_dirs:
            cards["POOLED-lat2x"] = pooled_card(lat_dirs)
    stop = quick_gate(cards) if a.stage == "quick" else None
    v = {"full": verdict, "lockbox": lockbox_verdict}.get(a.stage, lambda c: "n/a")(cards)
    if stop:
        v = "rejected at quick"
    elif a.stage == "quick":
        v = "passed"
    log(format_cards(cards))
    log(f"verdict: {v}")
    rep = RESULTS / "_jobs" / f"{job}.{a.stage}.json"
    rep.parent.mkdir(parents=True, exist_ok=True)
    rep.write_text(json.dumps(dict(job=job, stage=a.stage, strategy=spec, series=series, params=params,
                                   cards=cards, verdict=v, gate=stop, finished=datetime.now(UTC).isoformat()), indent=1))
    record(v, gate=stop)
    if stop:
        log(f"QUICK GATE: {stop}. Skipping the full test.")
        sys.exit(4)  # the worker stops the job here


def audit_compare(folder, stage, code, legacy_code, cards, verdict_, log):
    """Compare a fresh re-run with the strategy's latest ledger entry for this stage."""
    from .strategy_dir import ledger_runs
    rec = next((r for r in reversed(ledger_runs(folder.name)) if r.get("stage") == stage and not r.get("crashed")), None)
    if rec is None:
        log(f"AUDIT {stage}: no ledger entry to compare against")
        sys.exit(7)
    problems = []
    if rec.get("code_v") != 2:  # recorded with the v1 fingerprint (it included params/)
        code = legacy_code
    if rec.get("code") != code:
        problems.append(f"code changed since the recorded run ({rec.get('code')} -> {code})")
    if rec.get("verdict") != verdict_:
        problems.append(f"verdict differs: recorded {rec.get('verdict')}, re-run {verdict_}")
    a, b = (rec.get("cards") or {}).get("POOLED") or {}, cards.get("POOLED") or {}
    for k in ("pnl", "pnl_per_contract_c", "markets"):
        if a.get(k) is not None and b.get(k) is not None and abs(float(a[k]) - float(b[k])) > 1e-6 * max(1, abs(float(a[k]))):
            problems.append(f"{k}: recorded {a[k]}, re-run {b[k]}")
    if problems:
        log(f"AUDIT {stage}: MISMATCH (job {rec.get('job')}):\n  - " + "\n  - ".join(problems))
        sys.exit(8)
    log(f"AUDIT {stage}: matches the ledger (job {rec.get('job')}, verdict {verdict_}, POOLED {b})")


def audit(argv=None):
    """`kalshi-lab audit <slug> [--stages full,lockbox]`: independently re-run recorded stages and compare (before live)."""
    import argparse
    ap = argparse.ArgumentParser(prog="kalshi-lab audit")
    ap.add_argument("strategy")
    ap.add_argument("--stages", default="full,lockbox")
    a = ap.parse_args(argv)
    from .strategy_dir import folder_for, ledger_ok
    folder = folder_for(a.strategy)
    if folder is None:
        raise SystemExit("audit needs a strategy folder")
    print(f"ledger hash chain: {'ok' if ledger_ok(folder.name) else 'BROKEN'}")
    rc = 0
    for stage in a.stages.split(","):
        rc |= subprocess.call([sys.executable, "-m", "kalshi_lab", "validate", stage, a.strategy, "--audit",
                               "--job", f"audit-{folder.name}-{stage}-{datetime.now():%m%d%H%M%S}"], cwd=ROOT)
    sys.exit(rc)


def data_status(argv=None):
    """`kalshi-lab data [SERIES ...]`: what history exists locally and how it splits into development vs lockbox."""
    import argparse

    from .recorder.config import MARKETS, spot_map
    ap = argparse.ArgumentParser(prog="kalshi-lab data")
    ap.add_argument("series", nargs="*")
    a = ap.parse_args(argv)
    series = a.series or sorted(p.name for p in (BACKFILL / "kalshi").glob("*") if p.is_dir())
    print(f"lockbox starts {LOCKBOX_START:%Y-%m-%d}: never use data on/after it in research or ad-hoc backtests.\n")
    for s in series:
        days = backfill_days([s])
        rec = recorded_range([s])
        spot = spot_map([s], backfill=True).get(s, [])
        have_spot = [n for n in spot if (BACKFILL / "spot" / n).exists()]
        print(f"{s}: {'configured' if s in MARKETS else 'NOT in MARKETS config (trades only, no spot/recording)'}")
        if days:
            dev = [d for d in days if d < f"{LOCKBOX_START:%Y-%m-%d}"]
            print(f"  history  {days[0]} -> {days[-1]} ({len(days)} days) | development {len(dev)} days | "
                  f"lockbox {len(days) - len(dev)} days")
        else:
            print("  history  none (download: kalshi-lab backfill --series ... on the server, or ask the user)")
        print(f"  spot     {', '.join(have_spot) or 'none'}" + (f" (expected {spot})" if spot and not have_spot else ""))
        print(f"  books    {'recorded ' + rec[0].strftime('%Y-%m-%d') + ' -> ' + rec[1].strftime('%Y-%m-%d') if rec else 'not recorded'}")
        from .data.flow import FLOW, flow_sources
        for src in flow_sources(s).values():
            fd = sorted(p.stem for p in (FLOW / src).glob("*.parquet"))
            print(f"  flow     {src}: " + (f"{fd[0]} -> {fd[-1]} ({len(fd)} days)" if fd else
                                          "not on this laptop (kalshi-lab pull; if the server lacks it, ask the user)"))
