"""'Background work' section: backfills, validation jobs and paper runs, with elapsed time and estimates."""

import os
import re
from datetime import datetime, timezone
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
JOBS = ROOT / "results" / "_jobs"
LOGS = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "logs"
PAPER_GOAL = 350  # markets before judging a paper run

TS = re.compile(r"^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)")
PROGRESS = re.compile(r"\[(\d+)/(\d+)\]")
SPOT_DAY = re.compile(r"INFO backfill: (\w+) (\d{4}-\d\d-\d\d): \d+ (?:seconds|candles)")
STEP = re.compile(r"\[(\d+)/(\d+)\] (\S+) running (\S+):")


def _dur(sec) -> str:
    if sec is None:
        return "—"
    sec = int(sec)
    if sec < 90:
        return f"{sec}s"
    if sec < 5400:
        return f"{sec // 60}m"
    return f"{sec // 3600}h {sec % 3600 // 60:02d}m"


def _rate(points):
    """Units per second over recent (time, value) points."""
    if len(points) < 2:
        return 0.0
    (t0, v0), (t1, v1) = points[0], points[-1]
    dt = (t1 - t0).total_seconds()
    return (v1 - v0) / dt if dt > 0 else 0.0


@st.cache_data(ttl=30, show_spinner=False)
def _backfill_cached(path: str, mtime: float) -> dict | None:
    return backfill_progress(Path(path))


def backfill_progress(log: Path) -> dict | None:
    lines = log.read_text().splitlines()
    stamped = [(datetime.strptime(m[1], "%Y-%m-%d %H:%M:%S"), line) for line in lines if (m := TS.match(line))]
    if not stamped:
        return None
    start, (last_t, last) = stamped[0][0], stamped[-1]
    now = datetime.now()
    running = (now - last_t).total_seconds() < 600
    row = dict(kind="Backfill", name=log.stem.replace("backfill-", "").replace("-", " "), running=running,
               elapsed=((now if running else last_t) - start).total_seconds())
    recent = [(t, line) for t, line in stamped if (last_t - t).total_seconds() < 600]
    if m := PROGRESS.search(last):
        done, total = int(m[1]), int(m[2])
        rate = _rate([(t, int(x[1])) for t, line in recent if (x := PROGRESS.search(line))])
        row.update(phase="Kalshi trades", frac=done / total, detail=f"{done:,} / {total:,} markets",
                   eta=(total - done) / rate if rate > 0 else None)
    elif d := SPOT_DAY.search(last):
        days = [(t, datetime.fromisoformat(x[2])) for t, line in stamped if (x := SPOT_DAY.search(line))]
        first_day, day = days[0][1], days[-1][1]
        span = max(1, (now - first_day).days)
        left = max(0, (now - day).days)
        rate = _rate([(t, (dd - first_day).days) for t, dd in days if (last_t - t).total_seconds() < 600])
        row.update(phase=f"spot prices ({d[1]})", frac=1 - left / span, detail=f"at {d[2]}, {left} days to go",
                   eta=left / rate if rate > 0 else None, eta_note="then Kalshi trades")
    else:
        row.update(phase="starting", frac=0.0, detail="", eta=None)
    return row


def job_rows(jobs) -> list[dict]:
    rows = []
    for j in jobs:
        name = j["strategy"].split("/")[-1] + f" [{', '.join(j['series'])}]"
        if j["_state"] == "queued":
            rows.append(dict(kind="Test", name=name, phase="queued", frac=0.0,
                             detail=f"waiting for the worker · {', '.join(j['stages'])}", elapsed=None, eta=None))
            continue
        if j["_state"] != "running":
            continue
        log = JOBS / f"{j['id']}.log"
        stage_text = log.read_text().rsplit("=== ", 1)[-1] if log.exists() else ""
        steps = STEP.findall(stage_text)
        now = datetime.now(timezone.utc)
        elapsed = (now - datetime.fromisoformat(j["started"])).total_seconds() if j.get("started") else None
        stages = j["stages"]
        si = stages.index(j["stage"]) if j.get("stage") in stages else 0
        if steps:
            k, n, t0, run = steps[-1]
            run_el = (now - datetime.fromisoformat(t0).replace(tzinfo=timezone.utc)).total_seconds()
            frac = (si + (int(k) - 1) / int(n)) / len(stages)
            detail = f"{j['stage']}: run {k} of {n} ({run}, {_dur(run_el)} so far)"
        else:
            frac, detail = si / len(stages), f"{j.get('stage', '')}: starting"
        rows.append(dict(kind="Test", name=name, phase=f"stage {si + 1} of {len(stages)} ({j.get('stage', '')})",
                         frac=frac, detail=detail, elapsed=elapsed, eta=None,
                         eta_note="quick ≈ 5-10 min, full ≈ 30-60 min"))
    return rows


def paper_rows(papers) -> list[dict]:
    rows = []
    for p in papers:
        if not p["_running"]:
            continue
        try:
            start = datetime.fromisoformat(str(p["start"]))
            elapsed = (datetime.now(start.tzinfo) - start).total_seconds()
        except ValueError:
            elapsed = None
        n = p.get("markets_traded") or 0
        rate = n / elapsed if elapsed and n else 0
        rows.append(dict(kind="LIVE (real money)" if p.get("mode") == "live" else "Paper", name=str(p.get("strategy", "")).split("/")[-1] + f" [{', '.join(p.get('series', []))}]",
                         phase=f"{n} of ~{PAPER_GOAL} markets", frac=min(1.0, n / PAPER_GOAL),
                         detail=f"{n} markets traded so far", elapsed=elapsed,
                         eta=(PAPER_GOAL - n) / rate if rate else None,
                         eta_note="" if rate else "estimate after first trades"))
    return rows


def background_section(jobs, papers):
    rows = [r for log in sorted(LOGS.glob("backfill-*.log"))
            if (r := _backfill_cached(str(log), log.stat().st_mtime // 30)) and r["running"]]
    rows += job_rows(jobs) + paper_rows(papers)
    if not rows:
        return
    st.markdown("#### Background work")
    for r in rows:
        c1, c2, c3, c4 = st.columns([2.4, 3.4, 1.0, 1.7])
        c1.markdown(f"**{r['kind']}:** {r['name']}  \n<span style='font-size:0.8rem'>{r['phase']}</span>",
                    unsafe_allow_html=True)
        c2.progress(max(0.0, min(1.0, r["frac"])), text=r["detail"])
        c3.markdown(f"<span style='font-size:0.8rem'>running for</span>  \n**{_dur(r['elapsed'])}**", unsafe_allow_html=True)
        eta = f"~{_dur(r['eta'])} left" if r.get("eta") else (r.get("eta_note") or "—")
        if r.get("eta") and r.get("eta_note"):
            eta += f" · {r['eta_note']}"
        c4.markdown(f"<span style='font-size:0.8rem'>estimate</span>  \n**{eta}**", unsafe_allow_html=True)
    st.divider()
