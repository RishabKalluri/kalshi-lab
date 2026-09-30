"""Strategy pipeline page.

One card per strategy, always in the same layout:
  header + current status · what it does · what's running for it right now (tests, paper runs, data it
  waits on, with elapsed time and estimates) · stage tabs, each with what the stage checks, the result,
  and its numbers · next step.
Stage, descriptions and recorded numbers come from strategies/registry.json (kept current through chat);
live status comes from validation jobs, paper runs and backfill logs.
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
STAGES = ["idea", "research", "smoke", "quick", "full", "paper", "live"]
LABEL = {"idea": "Idea", "research": "Research", "smoke": "Smoke", "quick": "Quick", "full": "Full test",
         "paper": "Paper", "live": "Live", "rejected": "Rejected"}
STAGE_INFO = {
    "idea": "A hypothesis about why the market might be mispriced, and who's on the other side.",
    "research": "Quick analysis on historical data to see whether the effect exists at all. Screening only: research scripts simplify execution, so no decision is made on them (a +2.2c research result was -0.2c through the engine until entry timing was fixed).",
    "smoke": "Runs the strategy code on ~2 hours of data (~1 min): does it work, trade, and size orders sensibly? Must pass before anything else runs.",
    "quick": "A few days of history plus recent recorded order books (~5-10 min). A gate: clearly negative results stop here and the full test never runs.",
    "full": "Walk-forward through the real trading engine: one backtest per month, the strategy refit before each month on earlier data only, plus the last 3 months at double latency and all recorded order books (~30-60 min; only after Quick). Verdict from the pooled result: promising (CI above 0, >=60% of months up, survives 2x latency), reject, or inconclusive.",
    "paper": "Live market data, simulated money, 24/7 on the server. Checks that live fills and signals match the backtest. Can start once Quick passes and run alongside the Full test, since it risks no money.",
    "live": "Real money at small size with stop rules set in advance. Requires a finished Full test AND enough paper results, and your go-ahead.",
}
CARD_COLS = {"pnl": "PnL ($)", "markets": "markets", "contracts": "contracts", "pnl_per_contract_c": "¢/contract",
             "ci95_c": "95% CI (¢)", "days_positive": "days +", "max_drawdown": "max DD ($)"}


# ------------------------------------------------------------------ data (cached: the server is small)
def load_registry() -> list[dict]:
    p = ROOT / "strategies" / "registry.json"
    return json.loads(p.read_text()) if p.exists() else []


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


def _matches(entry, strategy: str, series) -> bool:
    return bool(entry["file"]) and strategy.split(":")[0].endswith(entry["file"]) and set(series) == set(entry["series"])


def resolve(entry, jobs, papers) -> dict:
    stage, status = entry["stage"], ""
    ejobs = [j for j in jobs if _matches(entry, j["strategy"], j["series"])]
    active = next((j for j in ejobs if j["_state"] in ("running", "queued")), None)
    paper = [p for p in papers if _matches(entry, p.get("strategy", ""), p.get("series", []))]
    live_paper = next((p for p in paper if p["_running"]), None)
    if active:
        stage = (active.get("stage") or active["stages"][0]) if active["_state"] == "running" else stage
        status = f"testing: {active.get('stage', '')}" if active["_state"] == "running" else "test queued"
    if live_paper:
        stage, status = "paper", "paper trading"
    if entry["stage"] == "rejected":
        status = "rejected"
    return dict(stage=stage, status=status, jobs=ejobs, active_job=active, paper=paper, live_paper=live_paper)


# ------------------------------------------------------------------ pieces
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


def activity_rows(entry, r, backfills) -> list[dict]:
    rows = job_rows(r["jobs"]) + paper_rows([p for p in r["paper"] if p["_running"]])
    for dep in entry.get("depends_on", []):
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
    m = Path(p["_dir"]) / "markets.csv"
    if m.exists():
        df = pd.read_csv(m, parse_dates=["settle_time"])
        df = df[df.fills > 0].sort_values("settle_time")
        if len(df) >= 2:
            df["cum"] = df.pnl.cumsum()
            fig = go.Figure(go.Scatter(x=df.settle_time, y=df.cum, mode="lines", line=dict(color=T["s1"], width=2),
                                       hovertemplate="%{y:$,.2f}<extra></extra>"))
            fig.add_hline(y=0, line=dict(color=T["axis"], width=1))
            st.markdown("**Paper PnL over time** (settled markets)")
            st.plotly_chart(layout(fig, 170, yfmt="$,.0f", legend=False), width="stretch", config={"displayModeBar": False})
    st.caption(f"results: `{Path(p['_dir']).name}` · saved {p['_age_min']:.0f} min ago")


def stage_tab(stage, entry, r, T, layout):
    h = entry.get("history", {}).get(stage)
    cur = STAGES.index(r["stage"]) if r["stage"] in STAGES else 0
    st.markdown(f"**What this stage checks:** {STAGE_INFO[stage]}")
    if h:
        st.markdown(f"**Result: {md(h['result'])}** · {h['date']}")
        st.markdown(md(h["detail"]))
    shown = False
    if h and h.get("metrics"):
        metric_grid(h["metrics"])
        shown = True
    cards = {name: run_card(name) for name in (h or {}).get("runs", [])}
    for j in r["jobs"]:  # automated pipeline reports for this stage
        rep = j.get("_reports", {}).get(stage)
        if rep:
            for run, c in rep["cards"].items():
                cards[f"{j['id']} · {run}"] = c
            if stage == "full":
                st.markdown(f"**Pipeline verdict:** {rep['verdict']}")
    if any(cards.values()):
        st.markdown("**Runs**")
        runs_table(cards)
        shown = True
    if stage == "paper" and r["paper"]:
        paper_stats(r["live_paper"] or r["paper"][0], T, layout)
        shown = True
    aj = r["active_job"]
    if aj and aj["_state"] == "running" and aj.get("stage") == stage:
        st.info("This stage is running now: progress is shown under Running now.")
    if not shown:
        st.caption("Not reached yet." if STAGES.index(stage) > cur else "No numbers recorded for this stage.")


def card(entry, r, backfills, T, layout):
    with st.container(border=True):
        h1, h2 = st.columns([3, 1.3])
        h1.markdown(f"### {entry['name']}")
        h1.caption(f"{', '.join(entry['series'])} · `{entry['file'] or 'research only'}` · "
                   f"stage: **{LABEL.get(r['stage'], r['stage'])}**")
        if r["status"]:
            h2.markdown(f'<div style="text-align:right;padding-top:0.9rem;color:{T["ink2"]}">{r["status"]}</div>',
                        unsafe_allow_html=True)
        st.markdown(f"**What it does:** {md(entry.get('description') or entry['summary'])}")
        rows = activity_rows(entry, r, backfills)
        if rows:
            st.markdown("**Running now**")
            activity_block(rows)
        cur = STAGES.index(r["stage"]) if r["stage"] in STAGES else 0
        hist = entry.get("history", {})

        def mark(i, s):
            if i == cur:
                return "◉"
            if hist.get(s, {}).get("status") == "partial":
                return "◐"
            return "✓" if i < cur else "○"

        labels = [f"{mark(i, s)} {LABEL[s]}" for i, s in enumerate(STAGES)]
        if entry.get("parallel_note"):
            st.caption(f"⇉ {entry['parallel_note']}")
        st.caption("Click a stage for its details and numbers · ✓ done · ◐ partly done · ◉ current · ○ not yet")
        tabs = st.tabs(labels, default=labels[cur], key=f"stages-{entry['id']}", on_change="ignore")
        for s, tab in zip(STAGES, tabs):
            with tab:
                stage_tab(s, entry, r, T, layout)
        if entry.get("next"):
            st.markdown(f"**Next:** {md(entry['next'])}")


# ------------------------------------------------------------------ page
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
    reg = load_registry()
    jobs, papers, backfills = _jobs(), _paper_runs(), _backfills()
    users = {}
    for e in reg:
        for d in e.get("depends_on", []):
            users.setdefault(d["log"], []).append(e["name"])
    running_bf = {k: v for k, v in backfills.items() if v["running"]}
    if running_bf:
        with st.expander(f"Data downloads ({len(running_bf)} running)"):
            for k, b in running_bf.items():
                c1, c2, c3 = st.columns([2.5, 4, 2])
                c1.markdown(f"**{b['name']}**  \n<span style='font-size:0.8rem'>for "
                            f"{', '.join(users.get(k, ['general history']))}</span>", unsafe_allow_html=True)
                c2.progress(max(0.0, min(1.0, b["frac"])), text=f"{b['phase']}: {b['detail']}")
                c3.markdown(f"running {_dur(b['elapsed'])}  \n**{'~' + _dur(b['eta']) + ' left' if b.get('eta') else '—'}**")
    st.divider()
    order = {s: i for i, s in enumerate(reversed(STAGES))}
    resolved = [(e, resolve(e, jobs, papers)) for e in reg if e["stage"] != "rejected"]
    resolved.sort(key=lambda x: order.get(x[1]["stage"], 99))
    for e, r in resolved:
        card(e, r, backfills, T, layout)
    rej = [e for e in reg if e["stage"] == "rejected"]
    if rej:
        with st.expander(f"Rejected ideas ({len(rej)})"):
            st.dataframe(pd.DataFrame([{"strategy": e["name"], "series": ", ".join(e["series"]),
                                        "what it was": e.get("description", e["summary"]), "why rejected": e["evidence"]}
                                       for e in rej]), hide_index=True, width="stretch")
