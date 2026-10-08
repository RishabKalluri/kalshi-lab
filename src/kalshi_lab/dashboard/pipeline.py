"""Strategy pipeline page: one card per strategy folder (strategies/<slug>/).

Each card reads the folder's config.json (name, description, hypothesis, status), results.json (every pipeline
run, appended automatically) and NOTES.md, plus live state: running test jobs, paper runs, data downloads.
Ideas without a folder and older rejected experiments come from strategies/_archive/registry.json.
"""

import json
import os
import subprocess
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from kalshi_lab.dashboard.background import _dur, backfill_progress, job_rows, paper_rows

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
JOBS = RESULTS / "_jobs"
DATA = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser()
LOGS = DATA.parent / "logs"
STAGES = ["idea", "research", "smoke", "quick", "full", "lockbox", "paper", "live"]
LABEL = {"idea": "Idea", "research": "Research", "smoke": "Smoke", "quick": "Quick", "full": "Full test",
         "lockbox": "Lockbox", "paper": "Paper", "live": "Live", "rejected": "Rejected", "parked": "Parked"}
STAGE_INFO = {
    "idea": "The hypothesis, written before any test: why the market should be mispriced and who's on the other side.",
    "research": "Screening analyses on history. They simplify execution, so no decision is made on them.",
    "smoke": "Runs the strategy on 6 hours of development data (~1 min): does it work, trade, and size orders sensibly?",
    "quick": "The last 3 days of development data (~1-10 min). Gate: clearly negative stops here; the full test never runs.",
    "full": "Walk-forward through the engine over all development months (before the lockbox), refit monthly on earlier data, plus the last 3 months at 2x latency. Promising = pooled 95% CI above 0, >=60% of months up, survives 2x latency. Budget: 3 per strategy.",
    "lockbox": "One shot at the ~6 weeks the strategy has never seen (from the lockbox date on), only after a promising full test. Pass = profitable; strong pass = CI above 0; fail = the idea is rejected, not tweaked.",
    "paper": "Live data, simulated money, 24/7 on the server, after the lockbox passes. Checks live fills and signals match the backtest.",
    "live": "Real money at small size with stop rules set in advance. Needs the user's go-ahead.",
}
CARD_COLS = {"pnl": "PnL ($)", "markets": "markets", "contracts": "contracts", "pnl_per_contract_c": "¢/contract",
             "ci95_c": "95% CI (¢)", "days_positive": "days +", "max_drawdown": "max DD ($)"}


# ------------------------------------------------------------------ data (cached: the server is small)
def load_entries() -> tuple[list[dict], list[dict]]:
    """(strategy folders, archived/legacy entries)."""
    from kalshi_lab.strategy_dir import all_folders, load_config, load_results
    out = []
    for f in all_folders():
        c = load_config(f)
        c["_folder"] = f
        c["_runs"] = load_results(f)["runs"]
        notes = f / "NOTES.md"
        c["_notes"] = notes.read_text() if notes.exists() else ""
        out.append(c)
    arch = ROOT / "strategies" / "_archive" / "registry.json"
    legacy = json.loads(arch.read_text()) if arch.exists() else []
    return out, [e for e in legacy if not any(e.get("id") == c["slug"] for c in out)]


@st.cache_data(ttl=20, show_spinner=False)
def _jobs() -> list[dict]:
    out = []
    for state in ("running", "queue", "done"):
        d = JOBS / state
        for f in d.glob("*.json") if d.exists() else []:
            j = json.loads(f.read_text())
            j["_state"] = {"queue": "queued"}.get(state, state)
            j["_mtime"] = f.stat().st_mtime
            for stage in ("quick", "full"):
                r = JOBS / f"{j['id']}.{stage}.json"
                if r.exists():
                    j.setdefault("_reports", {})[stage] = json.loads(r.read_text())
            out.append(j)
    return sorted(out, key=lambda j: j["_mtime"], reverse=True)


@st.cache_data(ttl=20, show_spinner=False)
def _paper_runs() -> list[dict]:
    out = []
    for f in RESULTS.glob("*/summary.json"):
        try:
            s = json.loads(f.read_text())
        except json.JSONDecodeError:
            continue
        if s.get("mode") not in ("paper", "live"):
            continue
        s["_dir"] = str(f.parent)
        s["_age_min"] = (time.time() - f.stat().st_mtime) / 60
        s["_running"] = s.get("end") == "(running)" and s["_age_min"] < 15
        out.append(s)
    return sorted(out, key=lambda s: str(s.get("start")), reverse=True)


@st.cache_data(ttl=120, show_spinner=False)
def run_card(name: str) -> dict | None:
    from kalshi_lab.validate import card
    d = RESULTS / name
    if not (d / "summary.json").exists():
        return None
    try:
        return card(d)
    except Exception:
        return None


@st.cache_data(ttl=20, show_spinner=False)
def health() -> list[tuple[str, bool, str]]:
    items = []
    papers = [f"kalshi-paper@{p.stem}" for p in sorted((ROOT / "deploy" / "paper").glob("*.json"))]
    for svc in ["kalshi-recorder", *papers, "kalshi-worker"]:
        label = {"kalshi-recorder": "Recorder", "kalshi-worker": "Test worker"}.get(svc, "Paper: " + svc.split("@")[-1])
        try:
            r = subprocess.run(["systemctl", "is-active", svc], capture_output=True, text=True, timeout=3)
            items.append((label, r.stdout.strip() == "active", r.stdout.strip() or "unknown"))
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
    newest = max((p.stat().st_mtime for p in (DATA / "kalshi_ws").glob("*/*/*.zst")), default=0)
    age = (time.time() - newest) / 60 if newest else None
    items.append(("Market data", age is not None and age < 5, f"updated {age:.0f} min ago" if age is not None else "none"))
    try:
        load = os.getloadavg()[0] / (os.cpu_count() or 1)
        items.append(("Server CPU", load < 1.0, f"{load:.0%} busy"))
    except OSError:
        pass
    return items


@st.cache_data(ttl=30, show_spinner=False)
def _backfills() -> dict[str, dict]:
    out = {}
    for log in sorted(LOGS.glob("backfill-*.log")):
        r = backfill_progress(log)
        if r:
            out[log.stem] = r
    return out


def _folder_of(spec: str):
    from kalshi_lab.strategy_dir import folder_for
    try:
        return folder_for(spec or "")
    except Exception:
        return None


def resolve(c, jobs, papers) -> dict:
    """Current stage + status for a strategy folder, from its results, config and live jobs/paper runs."""
    f = c["_folder"].resolve()
    runs = [r for r in c["_runs"] if not r.get("crashed")]
    reached = [STAGES.index(r["stage"]) for r in runs if r.get("stage") in STAGES]
    stage = STAGES[max(reached)] if reached else ("research" if "## Iteration log" in c["_notes"] and runs else "idea")
    status = c.get("status", "developing")
    ejobs = [j for j in jobs if _folder_of(j["strategy"]) == f]
    active = next((j for j in ejobs if j["_state"] in ("running", "queued")), None)
    paper = [p for p in papers if _folder_of(p.get("strategy", "")) == f]
    live_paper = next((p for p in paper if p["_running"]), None)
    label = status
    if status in ("paper", "live"):
        stage = status
    if active:
        label = f"testing: {active.get('stage', '')}" if active["_state"] == "running" else "test queued"
        if active["_state"] == "running" and active.get("stage") in STAGES:
            stage = max(stage, active["stage"], key=STAGES.index)
    elif live_paper:
        label = "paper trading"
    elif runs:
        last = runs[-1]
        label = f"{status} · last: {last['stage']} {last.get('verdict', '')}"
    return dict(stage=stage, status=label, jobs=ejobs, active_job=active, paper=paper, live_paper=live_paper, runs=runs)


def md(text: str) -> str:
    """Escape $ so Streamlit markdown doesn't render dollar amounts as LaTeX."""
    return str(text).replace("$", "\\$")


def _money(x):
    return "—" if x is None else f"{'-' if x < 0 else '+'}${abs(x):,.2f}"


def metric_grid(metrics: dict, per_row: int = 4):
    items = list(metrics.items())
    for i in range(0, len(items), per_row):
        cols = st.columns(per_row)
        for col, (k, v) in zip(cols, items[i:i + per_row]):
            col.metric(k, v)


def runs_table(cards: dict):
    rows = [{"run": name, **{CARD_COLS[k]: c.get(k) for k in CARD_COLS}} for name, c in cards.items() if c]
    if rows:
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")


def activity_rows(c, r, backfills) -> list[dict]:
    rows = job_rows(r["jobs"]) + paper_rows([p for p in r["paper"] if p["_running"]])
    for dep in c.get("depends_on", []):
        b = backfills.get(dep["log"])
        if b and b["running"]:
            rows.append({**b, "kind": "Waiting on data", "name": dep["label"]})
    return rows


def activity_block(rows):
    for a in rows:
        c1, c2, c3, c4 = st.columns([2.3, 3.4, 1.0, 1.8])
        sub = a["name"] if a["phase"] in a["name"] else f"{a['name']} · {a['phase']}"
        c1.markdown(f"**{a['kind']}**  \n<span style='font-size:0.8rem'>{sub}</span>",
                    unsafe_allow_html=True)
        c2.progress(max(0.0, min(1.0, a["frac"])), text=a["detail"])
        c3.markdown(f"<span style='font-size:0.8rem'>running for</span>  \n**{_dur(a['elapsed'])}**", unsafe_allow_html=True)
        eta = f"~{_dur(a['eta'])} left" if a.get("eta") else (a.get("eta_note") or "—")
        if a.get("eta") and a.get("eta_note"):
            eta += f" · {a['eta_note']}"
        c4.markdown(f"<span style='font-size:0.8rem'>estimate</span>  \n**{eta}**", unsafe_allow_html=True)


def _paper_key(p: dict) -> str:
    return json.dumps([_folder_of(p.get("strategy", "")), p.get("params"), p.get("sizing"), p.get("mode")], sort_keys=True, default=str)


def combine_paper(runs: list[dict]) -> dict | None:
    """Paper runs restart (deploys, a new API key, server reboots) and each restart writes a new results folder.
    Join the latest run with the earlier runs of the same strategy, params and sizing into one record."""
    if not runs:
        return None
    key = _paper_key(runs[0])  # runs are newest first
    seg = [r for r in runs if _paper_key(r) == key]
    if len(seg) == 1:
        return {**seg[0], "_dirs": [seg[0]["_dir"]]}
    tot = lambda k: sum((r.get(k) or 0) for r in seg)
    traded = tot("markets_traded")
    out = {**seg[0], "start": min(str(r.get("start")) for r in seg), "_dirs": [r["_dir"] for r in seg],
           "pnl": tot("pnl"), "fees": tot("fees"), "contracts": tot("contracts"), "markets_traded": traded,
           "orders": tot("orders"), "orders_filled": tot("orders_filled"), "orders_missed": tot("orders_missed"),
           "rejects": tot("rejects"), "markets_settled": tot("markets_settled"),
           "equity_change": tot("pnl") - (seg[0].get("pnl") or 0) + (seg[0].get("equity_change") or 0),
           "win_rate": (sum((r.get("win_rate") or 0) * (r.get("markets_traded") or 0) for r in seg) / traded) if traded else None}
    out["pnl_per_contract"] = out["pnl"] / out["contracts"] if out["contracts"] else None
    return out


def paper_stats(p: dict, T: dict, layout):
    el = None
    try:
        start = datetime.fromisoformat(str(p["start"]))
        el = (datetime.now(start.tzinfo) - start).total_seconds()
    except ValueError:
        pass
    wr, ppc = p.get("win_rate"), p.get("pnl_per_contract")
    st.markdown("**Paper trading so far**")
    metric_grid({
        "settled PnL": _money(p.get("pnl")),
        "incl. open positions": _money(p.get("equity_change")),
        "markets traded": f"{p.get('markets_traded', 0):,}",
        "¢/contract": f"{ppc * 100:+.2f}" if ppc is not None else "—",
        "win rate (markets)": f"{wr:.0%}" if wr is not None else "—",
        "contracts": f"{p.get('contracts', 0):,.0f}",
        "fees": f"${p.get('fees') or 0:,.2f}",
        "running for": _dur(el),
        "orders placed": f"{p.get('orders', '—')}",
        "orders filled": f"{p.get('orders_filled', '—')}",
        "orders missed": f"{p.get('orders_missed', '—')}",
        "risk rejects": f"{p.get('rejects', 0)}",
    })
    if p.get("orders_missed"):
        st.caption("Missed = the order reached the exchange after the price moved (immediate-or-cancel, unfilled).")
    dirs = p.get("_dirs") or [p["_dir"]]
    parts = [pd.read_csv(Path(d) / "markets.csv", parse_dates=["settle_time"]) for d in dirs if (Path(d) / "markets.csv").exists()]
    if parts:
        df = pd.concat(parts, ignore_index=True)
        df = df[df.fills > 0].sort_values("settle_time")
        if len(df) >= 2:
            df["cum"] = df.pnl.cumsum()
            fig = go.Figure(go.Scatter(x=df.settle_time, y=df.cum, mode="lines", line=dict(color=T["s1"], width=2),
                                       hovertemplate="%{y:$,.2f}<extra></extra>"))
            fig.add_hline(y=0, line=dict(color=T["axis"], width=1))
            st.markdown("**Paper PnL over time** (settled markets)")
            st.plotly_chart(layout(fig, 170, yfmt="$,.0f", legend=False), width="stretch", config={"displayModeBar": False})
    joined = f" · joined from {len(dirs)} runs (restarts) with the same settings" if len(dirs) > 1 else ""
    st.caption(f"results: `{Path(p['_dir']).name}`{joined} · saved {p['_age_min']:.0f} min ago")


def _pooled(rec: dict) -> dict:
    cards = rec.get("cards") or {}
    return cards.get("POOLED") or next((v for v in cards.values() if v), {}) or {}


def runs_history(stage_runs: list[dict]):
    """Every attempt at a stage, newest first, with its headline numbers."""
    rows = []
    for i, rec in enumerate(reversed(stage_runs)):
        pc = _pooled(rec)
        wf = [k for k, v in (rec.get("cards") or {}).items() if k.startswith(("wf-", "lockbox-2")) and v]
        up = sum((rec["cards"][k] or {}).get("pnl", 0) > 0 for k in wf)
        rows.append({"when": str(rec.get("finished", ""))[:16].replace("T", " "), "verdict": rec.get("verdict", ""),
                     "¢/contract": pc.get("pnl_per_contract_c"), "95% CI (¢)": pc.get("ci95_c"),
                     "PnL ($)": pc.get("pnl"), "markets": pc.get("markets"),
                     "months +": f"{up}/{len(wf)}" if wf else "", "note": rec.get("note", ""), "job": rec.get("job", "")})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    latest = stage_runs[-1]
    detail = {k: v for k, v in (latest.get("cards") or {}).items() if v}
    if len(detail) > 1:
        with st.expander("Latest attempt: every run"):
            runs_table(detail)


def stage_tab(stage, c, r, T, layout):
    cur = STAGES.index(r["stage"]) if r["stage"] in STAGES else 0
    st.markdown(f"**What this stage checks:** {md(STAGE_INFO[stage])}")
    stage_runs = [x for x in r["runs"] if x.get("stage") == stage]
    shown = False
    if stage == "idea":
        st.markdown(f"**Hypothesis:** {md(c.get('hypothesis', ''))}")
        shown = True
    elif stage == "research":
        sec = c["_notes"].split("## Ideas and prior work used")
        if len(sec) > 1:
            st.markdown(md(sec[1].split("\n## ")[0]))
            shown = True
    if stage_runs:
        for rec in stage_runs:
            if rec.get("pre_lockbox_rules") and stage == "lockbox":
                st.warning("**Spent, not an independent test.** " + md(rec.get("note", "")))
        if any(_pooled(x) for x in stage_runs):
            runs_history(stage_runs)
        shown = True
    if stage == "full":
        st.caption(f"Full tests used: {len(stage_runs)} of {c['budget'].get('full_tests', 3)}")
    if stage == "paper" and r["paper"]:
        paper_stats(combine_paper(r["paper"]), T, layout)
        shown = True
    aj = r["active_job"]
    if aj and aj["_state"] == "running" and aj.get("stage") == stage:
        st.info("This stage is running now: progress is shown under Running now.")
    if not shown:
        st.caption("Not reached yet." if STAGES.index(stage) > cur else "No runs recorded for this stage.")


def family_note(c):
    """Show the strategy's family (derived_from links) and flag a lockbox that wasn't independent."""
    from kalshi_lab.strategy_dir import family, family_lockbox_conflicts, family_root
    fam = sorted(family(c["slug"]) - {c["slug"]})
    if not fam:
        return
    root = family_root(c["slug"])
    parent = c.get("derived_from")
    st.caption(f"Family **{root}** ({len(fam) + 1} strategies: {', '.join(fam)})"
               + (f" · derived from `{parent}`" if parent else ""))
    for rec in c["_runs"]:
        if rec.get("stage") == "lockbox" and not rec.get("crashed"):
            series = rec.get("series") or c.get("series", [])
            earlier = family_lockbox_conflicts(c["slug"], series, rec.get("lockbox_start", ""), before=str(rec.get("finished")))
            if earlier:
                st.warning("**Lockbox not independent:** this family had already used the lockbox on the same markets ("
                           + "; ".join(earlier) + "), and this version was built after that result. Treat its lockbox like a "
                           "development result; paper trading is its real out-of-sample test.")


def card(c, r, backfills, T, layout):
    with st.container(border=True):
        h1, h2 = st.columns([3, 1.4])
        h1.markdown(f"### {c['name']}")
        h1.caption(f"{', '.join(c['series'])} · `strategies/{c['slug']}/` · stage: **{LABEL.get(r['stage'], r['stage'])}**")
        h2.markdown(f'<div style="text-align:right;padding-top:0.9rem;color:{T["ink2"]}">{r["status"]}</div>',
                    unsafe_allow_html=True)
        from kalshi_lab.strategy_dir import ledger_ok, results_match_ledger
        if not ledger_ok(c["slug"]):
            st.error("⚠ Ledger hash chain broken: pipeline records were edited. Treat every result for this strategy as untrusted.")
        elif not results_match_ledger(c["_folder"]):
            st.warning("⚠ results.json disagrees with the pipeline ledger (edited?). Numbers below may be wrong; "
                       "the ledger is authoritative.")
        st.markdown(f"**What it does:** {md(c.get('description', ''))}")
        family_note(c)
        rows = activity_rows(c, r, backfills)
        if rows:
            st.markdown("**Running now**")
            activity_block(rows)
        cur = STAGES.index(r["stage"]) if r["stage"] in STAGES else 0
        done_stages = {x["stage"] for x in r["runs"]}

        spent = {x["stage"] for x in r["runs"] if "spent" in str(x.get("verdict", ""))}

        def mark(i, s):
            if i == cur:
                return "◉"
            if i < cur:
                if s in spent:
                    return "◐"
                return "✓" if (s in done_stages or s in ("idea", "research")) else "◐"
            return "○"

        labels = [f"{mark(i, s)} {LABEL[s]}" for i, s in enumerate(STAGES)]
        st.caption("Click a stage for its details and numbers · ✓ done · ◐ skipped/partial · ◉ current · ○ not yet")
        tabs = st.tabs(labels, default=labels[cur], key=f"stages-{c['slug']}", on_change="ignore")
        for s, tab in zip(STAGES, tabs):
            with tab:
                stage_tab(s, c, r, T, layout)
        if c.get("next"):
            st.markdown(f"**Next:** {md(c['next'])}")
        with st.expander("Notes & learnings (NOTES.md)"):
            st.markdown(md(c["_notes"]) or "_empty_")


def page(T: dict, layout):
    st.title("Strategies")
    items = health()
    if items:
        cols = st.columns(len(items))
        for col, (label, ok, detail) in zip(cols, items):
            color, icon = ("#0ca30c", "●") if ok else ("#d03b3b", "▲")
            col.markdown(f'<div style="font-size:0.8rem;color:{T["muted"]}">{label}</div>'
                         f'<div style="font-size:0.85rem"><span style="color:{color}">{icon}</span> {detail}</div>',
                         unsafe_allow_html=True)
    entries, legacy = load_entries()
    jobs, papers, backfills = _jobs(), _paper_runs(), _backfills()
    running_bf = {k: v for k, v in backfills.items() if v["running"]}
    if running_bf:
        with st.expander(f"Data downloads ({len(running_bf)} running)"):
            for k, b in running_bf.items():
                c1, c2, c3 = st.columns([2.5, 4, 2])
                c1.markdown(f"**{b['name']}**")
                c2.progress(max(0.0, min(1.0, b["frac"])), text=f"{b['phase']}: {b['detail']}")
                c3.markdown(f"running {_dur(b['elapsed'])}  \n**{'~' + _dur(b['eta']) + ' left' if b.get('eta') else '—'}**")
    st.divider()
    active = [c for c in entries if c.get("status") not in ("rejected", "parked")]
    resolved = [(c, resolve(c, jobs, papers)) for c in active]
    order = {s: i for i, s in enumerate(reversed(STAGES))}
    from kalshi_lab.strategy_dir import family_root
    roots = {c["slug"]: family_root(c["slug"]) for c, _ in resolved}
    best = {}  # a family is listed where its most advanced member would be, members together
    for c, r in resolved:
        best[roots[c["slug"]]] = min(best.get(roots[c["slug"]], 99), order.get(r["stage"], 99))
    resolved.sort(key=lambda x: (best[roots[x[0]["slug"]]], roots[x[0]["slug"]], order.get(x[1]["stage"], 99)))
    if not resolved:
        st.info("No active strategies. Start one with the develop-strategy skill.")
    for c, r in resolved:
        card(c, r, backfills, T, layout)
    ideas = [e for e in legacy if e.get("stage") not in ("rejected",)]
    if ideas:
        with st.expander(f"Ideas without code yet ({len(ideas)})"):
            st.dataframe(pd.DataFrame([{"idea": e["name"], "markets": ", ".join(e["series"]),
                                        "what": e.get("description", e.get("summary", "")), "evidence": e.get("evidence", "")}
                                       for e in ideas]), hide_index=True, width="stretch")
    rej = [c for c in entries if c.get("status") in ("rejected", "parked")]
    rej_rows = [{"strategy": c["name"], "markets": ", ".join(c["series"]), "what it was": c.get("description", ""),
                 "why": c.get("next", ""), "folder": f"strategies/{c['slug']}/"} for c in rej]
    rej_rows += [{"strategy": e["name"], "markets": ", ".join(e["series"]), "what it was": e.get("description", e.get("summary", "")),
                  "why": e.get("evidence", ""), "folder": "strategies/_archive/"} for e in legacy if e.get("stage") == "rejected"]
    if rej_rows:
        with st.expander(f"Rejected or parked ({len(rej_rows)})"):
            st.dataframe(pd.DataFrame(rej_rows), hide_index=True, width="stretch")
