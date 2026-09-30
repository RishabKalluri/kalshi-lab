"""Staged strategy validation: smoke -> quick -> full, with a report card.

    kalshi-lab test strategies/my_idea.py --series KXETH15M [-p key=val ...]

runs `smoke` on the server in the foreground (~1 min) and, if it passes, queues `quick` and `full` on
the server's background worker (see jobs.py). Results appear in the dashboard's Jobs panel.

Stages (each is one or more ordinary backtests):
  smoke  recorded books, last 2 hours (or 6h of backfill): it runs, trades, isn't rejected by risk limits
  quick  backfill, last 3 days + recorded books, last 6 hours   (~5-10 min on the server). Gate: a clearly
         negative quick (all runs lose, a CI entirely below zero) stops the job before the full test.
  full   WALK-FORWARD over all backfilled months: one backtest per month. If the strategy defines
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


def plan(stage: str, series: list[str], fits: bool = False, min_train: int = 2) -> list[dict]:
    """The backtest runs (name + source + window + overrides) that make up a stage."""
    now = datetime.now(UTC).replace(second=0, microsecond=0)
    rec = recorded_range(series)
    days = backfill_days(series)
    runs = []
    if stage == "smoke":
        # Recorded books if there are at least 2 hours; otherwise the last 6 hours of backfill
        # (long enough for strategies that need ~1h of warm-up history).
        if rec and rec[1] - rec[0] >= timedelta(hours=2):
            runs.append(dict(name="smoke", source="recorded", start=rec[1] - timedelta(hours=2), end=rec[1]))
        elif days:
            d = datetime.fromisoformat(days[-1]).replace(tzinfo=UTC)
            runs.append(dict(name="smoke", source="backfill", start=d + timedelta(hours=18), end=d + timedelta(hours=24)))
    elif stage == "quick":
        if days:
            end = datetime.fromisoformat(days[-1]).replace(tzinfo=UTC) + timedelta(days=1)
            runs.append(dict(name="quick-backfill", source="backfill", start=end - timedelta(days=3), end=end,
                             fit_until=end - timedelta(days=3)))
        if rec:
            runs.append(dict(name="quick-recorded", source="recorded", start=max(rec[0], rec[1] - timedelta(hours=6)), end=rec[1]))
    elif stage == "full":
        if days:
            first = datetime.fromisoformat(days[0]).replace(tzinfo=UTC)
            last = datetime.fromisoformat(days[-1]).replace(tzinfo=UTC) + timedelta(days=1)
            months, m = [], first.replace(day=1)
            while m < last:
                nxt = (m + timedelta(days=32)).replace(day=1)
                s0, e0 = max(m, first), min(nxt, last)
                # skip slivers and the first `min_train` months (they're training data for fit())
                if (e0 - s0) >= timedelta(days=5):
                    months.append((s0, e0))
                m = nxt
            train_months = min_train if fits else 0
            for s0, e0 in months[train_months:]:
                runs.append(dict(name=f"wf-{s0:%Y-%m}", source="backfill", start=s0, end=e0, fit_until=s0))
            for s0, e0 in months[train_months:][-3:]:
                runs.append(dict(name=f"lat2x-{s0:%Y-%m}", source="backfill", start=s0, end=e0, fit_until=s0,
                                 latency_ms=300))
        if rec:
            runs.append(dict(name="full-recorded", source="recorded", start=rec[0], end=rec[1],
                             fit_until=rec[0]))
    else:
        raise ValueError(stage)
    return runs


def run_backtest(strategy: str, series: list[str], params: list[str], r: dict, out: Path, log, i=1, n=1) -> dict | None:
    params = list(params) + [f"{k}={v}" for k, v in r.get("params", {}).items()]
    cmd = [sys.executable, "-m", "kalshi_lab", "backtest", strategy, "--series", *series, "--source", r["source"],
           "--start", r["start"].isoformat(), "--end", r["end"].isoformat(), "--out", str(out),
           "--latency-ms", str(r.get("latency_ms", 150)), "--workers", "1"]
    for p in params:
        cmd += ["-p", p]
    log(f"  [{i}/{n}] {datetime.now(UTC):%Y-%m-%dT%H:%M:%S} running {r['name']}: {r['source']} "
        f"{r['start']:%m-%d %H:%M} -> {r['end']:%m-%d %H:%M}")
    proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
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


def main(argv=None):
    """Server side: `kalshi-lab validate smoke|quick|full <strategy> --series ... [-p ...] [--job ID]`."""
    import argparse
    ap = argparse.ArgumentParser(prog="kalshi-lab validate")
    ap.add_argument("stage", choices=["smoke", "quick", "full"])
    ap.add_argument("strategy")
    ap.add_argument("--series", nargs="+", default=["KXBTC15M"])
    ap.add_argument("-p", "--param", action="append", default=[])
    ap.add_argument("--job", default=None, help="job id (names the result dirs)")
    a = ap.parse_args(argv)
    job = a.job or f"{Path(a.strategy.split(':')[0]).stem}-{datetime.now():%m%d-%H%M%S}"
    log = lambda s: print(s, flush=True)
    from .backtest import load_strategy
    cls = load_strategy(a.strategy)
    fits = callable(getattr(cls, "fit", None))
    runs = plan(a.stage, a.series, fits=fits)
    if not runs:
        log(f"no data for {a.series} to run the {a.stage} stage")
        sys.exit(2)
    user_keys = {p.split("=", 1)[0] for p in a.param}
    if fits:  # refit on data before each window; user -p overrides win
        cache = {}
        for r in runs:
            until = r.get("fit_until")
            key = until.isoformat() if until else None
            if key not in cache:
                log(f"  fit: data before {key or 'now'}")
                cache[key] = cls.fit(a.series, key)
            r["params"] = {k: v for k, v in cache[key].items() if k not in user_keys}
    cards = {}
    workers = int(os.environ.get("KALSHI_TEST_WORKERS", max(1, (os.cpu_count() or 2) - 2)))
    log(f"plan: {len(runs)} runs, {workers} at a time")

    def one(i_r):
        i, r = i_r
        out = RESULTS / f"{job}-{r['name']}"
        return r["name"], out, run_backtest(a.strategy, a.series, a.param, r, out, log, i, len(runs))

    with ThreadPoolExecutor(max_workers=1 if a.stage == "smoke" else workers) as pool:
        results = list(pool.map(one, enumerate(runs, 1)))
    for name, out, s in results:
        if s is None:
            sys.exit(1)
        cards[name] = card(out)
        if a.stage == "smoke":
            problems = smoke_checks(s)
            log(format_cards(cards))
            if problems:
                log("SMOKE FAILED:\n  - " + "\n  - ".join(problems))
                sys.exit(3)
            log("smoke passed")
    if a.stage == "full":
        wf_dirs = [out for name, out, _ in results if name.startswith("wf-")]
        lat_dirs = [out for name, out, _ in results if name.startswith("lat2x-")]
        cards["POOLED"] = pooled_card(wf_dirs)
        if lat_dirs:
            cards["POOLED-lat2x"] = pooled_card(lat_dirs)
    if a.stage != "smoke":
        v = verdict(cards) if a.stage == "full" else "n/a"
        stop = quick_gate(cards) if a.stage == "quick" else None
        if stop:
            v = "rejected at quick"
        log(format_cards(cards))
        log(f"verdict: {v}")
        rep = RESULTS / "_jobs" / f"{job}.{a.stage}.json"
        rep.parent.mkdir(parents=True, exist_ok=True)
        rep.write_text(json.dumps(dict(job=job, stage=a.stage, strategy=a.strategy, series=a.series, params=a.param,
                                       cards=cards, verdict=v, gate=stop, finished=datetime.now(UTC).isoformat()), indent=1))
        if stop:
            log(f"QUICK GATE: {stop}. Skipping the full test.")
            sys.exit(4)  # the worker stops the job here
