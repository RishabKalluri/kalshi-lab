"""Backtest dashboard: run strategies and inspect results.

    uv run kalshi-lab dashboard
"""

import json
import math
import os
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

ROOT = Path(__file__).resolve().parents[3]
RESULTS = ROOT / "results"
STRATEGIES = ROOT / "strategies"
DATA = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser()
BACKFILL = DATA.parent / "backfill"

st.set_page_config(page_title="kalshi-lab", layout="wide")

# ---------------------------------------------------------------- theme tokens
LIGHT = dict(surface="#fcfcfb", ink="#0b0b0b", ink2="#52514e", muted="#898781", grid="#e1e0d9",
             axis="#c3c2b7", s1="#2a78d6", s2="#eb6834", s3="#1baf7a", s4="#eda100", pos="#2a78d6", neg="#e34948",
             band="rgba(42,120,214,0.08)")
DARK = dict(surface="#1a1a19", ink="#ffffff", ink2="#c3c2b7", muted="#898781", grid="#2c2c2a",
            axis="#383835", s1="#3987e5", s2="#d95926", s3="#199e70", s4="#c98500", pos="#3987e5", neg="#e66767",
            band="rgba(57,135,229,0.12)")


def theme():
    kind = getattr(getattr(st.context, "theme", None), "type", None) or "light"
    return DARK if kind == "dark" else LIGHT


T = theme()
FONT = 'system-ui, -apple-system, "Segoe UI", sans-serif'


def layout(fig: go.Figure, height=320, yfmt=None, ytitle=None, legend=True):
    fig.update_layout(
        height=height, margin=dict(l=8, r=8, t=28, b=8), paper_bgcolor=T["surface"], plot_bgcolor=T["surface"],
        font=dict(family=FONT, color=T["ink2"], size=12), hovermode="x unified",
        hoverlabel=dict(bgcolor=T["surface"], font=dict(color=T["ink"], family=FONT), bordercolor=T["axis"]),
        showlegend=legend, legend=dict(orientation="h", yanchor="bottom", y=1.0, x=0, font=dict(color=T["ink2"])),
    )
    ax = dict(showgrid=True, gridcolor=T["grid"], gridwidth=1, zeroline=False, linecolor=T["axis"],
              tickfont=dict(color=T["muted"]), title_font=dict(color=T["muted"]))
    fig.update_xaxes(**ax, showspikes=True, spikecolor=T["axis"], spikethickness=1, spikedash="solid",
                     spikemode="across")
    fig.update_yaxes(**ax, tickformat=yfmt, title_text=ytitle)
    return fig


def show(fig):
    st.plotly_chart(fig, width="stretch", config={"displayModeBar": False})


# ---------------------------------------------------------------- discovery
@st.cache_data(ttl=30)
def find_strategies() -> dict[str, dict]:
    """'strategies/file.py:Class' -> its default params (+ module docstring), for every Strategy subclass."""
    import importlib.util

    from kalshi_lab.strategy import Strategy
    out = {}
    for f in sorted(STRATEGIES.glob("*.py")):
        try:
            spec = importlib.util.spec_from_file_location(f"dash_{f.stem}", f)
            mod = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(mod)
        except Exception as e:
            out[f"strategies/{f.name}"] = {"__error__": repr(e)}
            continue
        for v in vars(mod).values():
            if isinstance(v, type) and issubclass(v, Strategy) and v is not Strategy and v.__module__ == mod.__name__:
                out[f"strategies/{f.name}:{v.__name__}"] = {**v.params, "__doc__": (mod.__doc__ or "").strip()}
    return out


@st.cache_data(ttl=60)
def data_coverage() -> dict:
    cov = {}
    for s in ("KXBTC15M", "KXETH15M", "KXGOLD15M"):
        rec = sorted((DATA / "kalshi_ws" / s).glob("*/*.jsonl.zst"))
        bf = sorted((BACKFILL / "kalshi" / s).glob("*"))
        cov[s] = {
            "recorded": (rec[0].parent.name + " " + rec[0].name[:2] + ":00", rec[-1].parent.name + " " + rec[-1].name[:2] + ":59") if rec else None,
            "recorded_hours": len(rec),
            "backfill": (bf[0].name, bf[-1].name) if bf else None,
            "backfill_days": len(bf),
        }
    return cov


def list_runs() -> list[Path]:
    if not RESULTS.exists():
        return []
    runs = [p for p in RESULTS.iterdir() if p.is_dir() and not p.name.startswith("_")
            and ((p / "summary.json").exists() or any((c / "summary.json").exists() for c in p.iterdir() if c.is_dir()))]
    return sorted(runs, key=lambda p: p.stat().st_mtime, reverse=True)


def is_sweep(p: Path) -> bool:
    return not (p / "summary.json").exists()


@st.cache_data(ttl=10)
def load_run(path: str, mtime: float):
    p = Path(path)
    summary = json.loads((p / "summary.json").read_text())
    markets = pd.read_csv(p / "markets.csv", parse_dates=["settle_time", "open_time", "close_time"])
    fills = pd.read_csv(p / "fills.csv", parse_dates=["time"])
    tl = p / "timeline.csv.gz"
    timeline = pd.read_csv(tl, parse_dates=["time"]) if tl.exists() else None
    return summary, markets, fills, timeline


# ---------------------------------------------------------------- run panel
def run_panel():
    strategies = find_strategies()
    cov = data_coverage()
    with st.container():
        st.header("Run a backtest")
        if not strategies:
            st.info("No strategies found in strategies/.")
            return
        spec = st.selectbox("Strategy", list(strategies), index=_default_strategy(strategies))
        info = strategies[spec]
        if "__error__" in info:
            st.error(f"Couldn't load: {info['__error__']}")
            return
        if info.get("__doc__"):
            with st.expander("About this strategy"):
                st.markdown(info["__doc__"])
        source = st.radio("Data", ["recorded", "backfill"], horizontal=True,
                          help="recorded: full order books (most realistic). backfill: trades + 1s spot, no book.")
        series = st.multiselect("Series", list(cov), default=["KXBTC15M"])
        c = cov.get(series[0] if series else "KXBTC15M", {})
        rng = c.get(source) if source == "recorded" else c.get("backfill")
        st.caption(f"Available {source}: {rng[0]} → {rng[1]} UTC" if rng else f"No {source} data yet")
        now = datetime.now(timezone.utc).replace(second=0, microsecond=0)
        default_start = now - (timedelta(hours=6) if source == "recorded" else timedelta(days=14))
        c1, c2 = st.columns(2)
        sd = c1.date_input("Start (UTC)", default_start.date())
        stime = c2.time_input("at", default_start.time(), key="st")
        c3, c4 = st.columns(2)
        ed = c3.date_input("End (UTC)", now.date())
        etime = c4.time_input("at", now.time(), key="et")

        st.subheader("Parameters")
        params = {}
        for k, v in info.items():
            if k.startswith("__"):
                continue
            if isinstance(v, bool):
                params[k] = st.checkbox(k, v)
            elif isinstance(v, int):
                params[k] = st.number_input(k, value=v, step=1)
            elif isinstance(v, float):
                params[k] = st.number_input(k, value=v, format="%g")
            else:
                params[k] = st.text_input(k, str(v))
        sweep = st.text_input("Sweep (optional)", placeholder="edge=20,40,60; size=5,10",
                              help="Runs every combination in parallel and compares them.")
        st.subheader("Sizing")
        policy = st.selectbox("Policy", ["1% of equity per order (default)", "fixed contracts", "fixed $ risk",
                                         "fractional Kelly"],
                              help="Strategy-agnostic: every strategy asks ctx.size() and this policy answers.")
        if policy.startswith("1%"):
            sizing = "pct:1"
        elif policy == "fixed contracts":
            sizing = f"fixed:{st.number_input('Contracts per order', value=10, step=1)}"
        elif policy == "fixed $ risk":
            sizing = f"risk:{st.number_input('Max loss per order ($)', value=25, step=5)}"
        else:
            sizing = f"kelly:{st.number_input('Kelly fraction', value=0.25, step=0.05, format='%.2f')}"
        s1, s2 = st.columns(2)
        bankroll = s1.number_input("Bankroll ($)", value=1000, step=100)
        max_frac = s2.number_input("Max % per market", value=5, step=1) / 100
        with st.expander("Execution & risk"):
            latency = st.number_input("Latency (ms)", value=150, step=50)
            queue = st.slider("Queue position for resting orders", 0.0, 1.0, 1.0, 0.1,
                              help="1.0 = join behind everything already resting (conservative). 0.5 = halfway.")
            max_pos = st.number_input("Max position / market", value=500, step=50)
            max_qty = st.number_input("Max order qty", value=100, step=10)
        name = st.text_input("Run name", f"{Path(spec.split(':')[0]).stem}-{datetime.now():%m%d-%H%M%S}")
        if st.button("Run backtest", type="primary", width="stretch", disabled=not series):
            start = datetime.combine(sd, stime).isoformat()
            end = datetime.combine(ed, etime).isoformat()
            cmd = ["uv", "run", "kalshi-lab", "backtest", spec, "--source", source, "--series", *series,
                   "--start", start, "--end", end, "--latency-ms", str(latency), "--queue-frac", str(queue), "--max-position", str(max_pos),
                   "--max-order-qty", str(max_qty), "--sizing", sizing, "--bankroll", str(bankroll),
                   "--max-frac", str(max_frac), "--out", str(RESULTS / name)]
            for k, v in params.items():
                if v != info[k]:
                    cmd += ["-p", f"{k}={json.dumps(v) if not isinstance(v, str) else v}"]
            for part in [x.strip() for x in sweep.split(";") if x.strip()]:
                cmd += ["--sweep", part.replace(" ", "")]
            with st.status(f"Running {name}…", expanded=True) as status:
                st.code(" ".join(shlex.quote(c) for c in cmd), language="bash")
                proc = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
                st.code((proc.stdout + proc.stderr)[-4000:] or "(no output)")
                if proc.returncode == 0:
                    status.update(label=f"Done: {name}", state="complete")
                    st.session_state["run"] = name
                    st.rerun()
                else:
                    status.update(label="Backtest failed", state="error")


def _default_strategy(strategies) -> int:
    keys = list(strategies)
    for i, k in enumerate(keys):
        if "template" not in k:
            return i
    return 0


# ---------------------------------------------------------------- results
def money(x):
    return "—" if x is None or (isinstance(x, float) and math.isnan(x)) else f"{'-' if x < 0 else ''}${abs(x):,.2f}"


def tiles(s: dict):
    cols = st.columns(6)
    cols[0].metric("Net PnL", money(s.get("pnl")), help="Settled markets, after fees")
    cols[1].metric("Before fees", money(s.get("pnl_before_fees")))
    cols[2].metric("Fees", money(s.get("fees")))
    cols[3].metric("Markets traded", f"{s.get('markets_traded', 0)} / {s.get('markets_settled', 0)}")
    wr = s.get("win_rate")
    cols[4].metric("Win rate", f"{wr:.0%}" if wr is not None else "—")
    t = s.get("t_stat")
    cols[5].metric("t-stat", f"{t:.2f}" if t is not None else "—", help="Mean PnL per traded market ÷ its standard error")
    cols = st.columns(6)
    cols[0].metric("Contracts", f"{s.get('contracts', 0):,.0f}")
    ppc = s.get("pnl_per_contract")
    cols[1].metric("PnL / contract", f"{ppc * 100:.2f}¢" if ppc is not None else "—")
    ms = s.get("maker_share")
    cols[2].metric("Maker share", f"{ms:.0%}" if ms is not None else "—")
    cols[3].metric("Max drawdown", money(s.get("max_drawdown")))
    cols[4].metric("Fills", f"{s.get('fills', 0):,}")
    cols[5].metric("Return on bankroll", f"{s['return_pct']:+.2f}%" if s.get("return_pct") is not None else "—",
                   help=f"bankroll ${s.get('bankroll', 0):,.0f}; rejects {s.get('rejects', 0)}")


def equity_chart(markets: pd.DataFrame):
    m = markets.sort_values("settle_time")
    m["cum"] = m["pnl"].cumsum()
    fig = go.Figure(go.Scatter(x=m["settle_time"], y=m["cum"], mode="lines", name="Cumulative PnL",
                               line=dict(color=T["s1"], width=2), hovertemplate="%{y:$,.2f}<extra></extra>"))
    fig.add_hline(y=0, line=dict(color=T["axis"], width=1))
    last = m.iloc[-1] if len(m) else None
    if last is not None:
        fig.add_annotation(x=last["settle_time"], y=last["cum"], text=money(last["cum"]), showarrow=False,
                           xanchor="left", xshift=6, font=dict(color=T["ink"]))
    st.markdown("**Cumulative PnL** · by settlement time")
    show(layout(fig, 300, yfmt="$,.0f", legend=False))


def per_market_chart(traded: pd.DataFrame):
    t = traded.sort_values("close_time")
    colors = [T["pos"] if v >= 0 else T["neg"] for v in t["pnl"]]
    fig = go.Figure(go.Bar(x=t["close_time"], y=t["pnl"], marker=dict(color=colors, line=dict(width=0)),
                           customdata=t[["ticker", "result", "volume"]],
                           hovertemplate="%{customdata[0]}<br>PnL %{y:$,.2f} · result %{customdata[1]}"
                                         " · %{customdata[2]:,.0f} contracts<extra></extra>"))
    fig.update_layout(bargap=0.15, hovermode="closest")
    fig.add_hline(y=0, line=dict(color=T["axis"], width=1))
    st.markdown("**PnL per market** · blue = profit, red = loss")
    show(layout(fig, 260, yfmt="$,.0f", legend=False))


def market_detail(ticker: str, markets: pd.DataFrame, fills: pd.DataFrame, timeline: pd.DataFrame | None):
    m = markets[markets.ticker == ticker].iloc[0]
    f = fills[fills.ticker == ticker]
    c = st.columns(5)
    c[0].metric("Result", "OPEN" if m["result"] == "open" else str(m["result"]).upper())
    c[1].metric("PnL", "unsettled" if m["result"] == "open" else money(m["pnl"]))
    c[2].metric("Strike", f"{m['strike']:,.2f}" if pd.notna(m["strike"]) else "—")
    c[3].metric("Settled at", f"{m['settle_value']:,.2f}" if pd.notna(m["settle_value"]) else "—")
    c[4].metric("Contracts", f"{m['volume']:,.0f}")
    if timeline is None:
        st.info("This run has no timeline (run with --timeline-s > 0 to chart prices).")
        return
    tl = timeline[timeline.ticker == ticker]
    if tl.empty:
        st.info("No timeline samples for this market.")
        return
    close = m["close_time"] if m["result"] != "open" else None
    fig = go.Figure()
    if close is not None:
        fig.add_vrect(x0=close - pd.Timedelta(seconds=60), x1=close, fillcolor=T["band"], line_width=0,
                      annotation_text="settlement window", annotation_position="top left",
                      annotation_font=dict(color=T["muted"], size=11))
    for col, name, color in (("bid", "YES bid", T["s1"]), ("ask", "YES ask", T["s2"])):
        fig.add_trace(go.Scatter(x=tl["time"], y=tl[col] / 1000, name=name, mode="lines",
                                 line=dict(color=color, width=2, shape="hv"), hovertemplate="%{y:.3f}"))
    for extra, color, name in (("fair", T["s3"], "Strategy reference"), ("model", T["s4"], "Spot model")):
        if extra in tl and tl[extra].notna().any():
            fig.add_trace(go.Scatter(x=tl["time"], y=tl[extra] / 1000, name=name, mode="lines",
                                     line=dict(color=color, width=2), hovertemplate="%{y:.3f}"))
    for side, symbol, label in (("buy", "triangle-up", "Buy YES"), ("sell", "triangle-down", "Sell YES")):
        ff = f[f.side == side]
        if len(ff):
            fig.add_trace(go.Scatter(
                x=ff["time"], y=ff["price"] / 1000, mode="markers", name=label,
                marker=dict(symbol=symbol, size=11, color=T["ink"], line=dict(color=T["surface"], width=2)),
                customdata=ff[["qty", "fee", "maker"]],
                hovertemplate=label + " %{customdata[0]:.0f} @ %{y:.3f} · fee $%{customdata[1]:.2f}"
                                      " · maker %{customdata[2]}<extra></extra>"))
    st.markdown("**YES price** · order book and fills")
    show(layout(fig, 340, yfmt=".2f"))

    fig = go.Figure()
    if close is not None:
        fig.add_vrect(x0=close - pd.Timedelta(seconds=60), x1=close, fillcolor=T["band"], line_width=0)
    fig.add_trace(go.Scatter(x=tl["time"], y=tl["spot"], name="Spot (composite)", mode="lines",
                             line=dict(color=T["s1"], width=2), hovertemplate="%{y:,.2f}"))
    if pd.notna(m["strike"]):
        fig.add_hline(y=m["strike"], line=dict(color=T["muted"], width=1),
                      annotation_text=f"strike {m['strike']:,.2f}", annotation_position="top left",
                      annotation_font=dict(color=T["muted"], size=11))
    st.markdown("**Underlying** · YES wins if the closing 60s average ≥ strike")
    show(layout(fig, 240, yfmt=",.0f", legend=False))


def sweep_view(p: Path):
    rows = []
    for c in sorted(q for q in p.iterdir() if (q / "summary.json").exists()):
        s = json.loads((c / "summary.json").read_text())
        rows.append({"config": c.name, **{k: s.get(k) for k in ("pnl", "pnl_before_fees", "fees", "contracts",
                                                                "markets_traded", "win_rate", "t_stat", "max_drawdown")}})
    df = pd.DataFrame(rows)
    if df.empty:
        st.info("Empty sweep.")
        return None
    df = df.sort_values("pnl", ascending=False)
    colors = [T["pos"] if v >= 0 else T["neg"] for v in df["pnl"]]
    fig = go.Figure(go.Bar(x=df["pnl"], y=df["config"], orientation="h", marker=dict(color=colors, line=dict(width=0)),
                           hovertemplate="%{y}: %{x:$,.2f}<extra></extra>"))
    fig.update_layout(hovermode="closest", bargap=0.2)
    fig.update_yaxes(autorange="reversed")
    st.markdown("**Net PnL by configuration**")
    show(layout(fig, max(200, 34 * len(df) + 60), yfmt=None, legend=False).update_xaxes(tickformat="$,.0f"))
    st.dataframe(df, hide_index=True, width="stretch",
                 column_config={"pnl": st.column_config.NumberColumn(format="$%.2f"),
                                "pnl_before_fees": st.column_config.NumberColumn(format="$%.2f"),
                                "fees": st.column_config.NumberColumn(format="$%.2f"),
                                "max_drawdown": st.column_config.NumberColumn(format="$%.2f"),
                                "win_rate": st.column_config.NumberColumn(format="percent")})
    return st.selectbox("Open configuration", df["config"].tolist())


def results_panel():
    runs = list_runs()
    if not runs:
        st.info("No results yet. Run a backtest from the sidebar.")
        return
    names = [r.name for r in runs]
    default = names.index(st.session_state["run"]) if st.session_state.get("run") in names else 0
    pick = st.selectbox("Run", names, index=default, label_visibility="collapsed")
    p = RESULTS / pick
    if is_sweep(p):
        st.subheader(f"Sweep · {pick}")
        child = sweep_view(p)
        if not child:
            return
        p = p / child
        st.divider()
    summary, markets, fills, timeline = load_run(str(p), (p / "summary.json").stat().st_mtime)
    running = summary.get("end") == "(running)"
    if running:
        age = datetime.now().timestamp() - (p / "summary.json").stat().st_mtime
        c1, c2 = st.columns([5, 1])
        c1.success(f"**{summary.get('mode', 'paper').upper()} run in progress** · results saved {age / 60:.0f} min ago "
                   f"(every 5 min) · equity change {money(summary.get('equity_change'))} incl. open positions · "
                   f"open: {summary.get('open_positions') or 'none'}")
        if c2.button("Refresh", width="stretch"):
            st.cache_data.clear()
            st.rerun()
    meta = f"{summary.get('strategy', '')} · {summary.get('source', '')} · {', '.join(summary.get('series', []))}"
    st.caption(f"{meta} · {str(summary.get('start', ''))[:16]} → {str(summary.get('end', ''))[:16]} UTC · "
               f"latency {summary.get('latency_ms')}ms · queue {summary.get('queue_frac', 1.0)} · sizing {summary.get('sizing') or 'fixed:10'} · params {summary.get('resolved_params') or summary.get('params')}")
    tiles(summary)
    traded = markets[markets.fills > 0]
    # Markets with fills that haven't settled yet (live/paper runs, or a backtest that ended mid-market).
    open_tk = sorted(set(fills.ticker) - set(markets.ticker))
    if open_tk:
        extra = []
        for tk in open_tk:
            f = fills[fills.ticker == tk]
            tl = timeline[timeline.ticker == tk] if timeline is not None else pd.DataFrame()
            close = pd.Timestamp(tl.time.max()) if len(tl) else f.time.max()
            extra.append(dict(settle_time=pd.NaT, ticker=tk, open_time=pd.NaT, close_time=close,
                              strike=tl.strike.dropna().iloc[-1] if len(tl) and tl.strike.notna().any() else float("nan"),
                              settle_value=float("nan"), result="open", pnl=float("nan"), fees=f.fee.sum(),
                              fills=len(f), volume=f.qty.sum(), maker_qty=f[f.maker].qty.sum(),
                              taker_qty=f[~f.maker].qty.sum(), final_pos=float("nan")))
        markets = pd.concat([markets, pd.DataFrame(extra)], ignore_index=True)
        traded = markets[markets.fills > 0]
    if traded.empty:
        st.info("No fills yet." if running else "No trades in this run.")
        return
    tab_charts, tab_market, tab_tables = st.tabs(["Overview", "Market detail", "Tables"])
    settled = markets[markets.result != "open"]
    with tab_charts:
        if settled[settled.fills > 0].empty:
            st.info("No market has settled yet. Open markets are in Market detail.")
        else:
            equity_chart(settled)
            per_market_chart(settled[settled.fills > 0])
    with tab_market:
        order = traded.reindex(traded.pnl.abs().sort_values(ascending=False).index)
        order = pd.concat([order[order.result == "open"], order[order.result != "open"]])
        labels = {t: f"{t}  ·  {'open' if r == 'open' else money(p)}  ·  {'' if r == 'open' else r}"
                  for t, p, r in zip(order.ticker, order.pnl, order.result)}
        ticker = st.selectbox("Market (largest |PnL| first)", list(labels), format_func=labels.get)
        market_detail(ticker, markets, fills, timeline)
    with tab_tables:
        st.markdown("**Markets traded**")
        st.dataframe(traded.drop(columns=["open_time"]), hide_index=True, width="stretch")
        st.markdown("**Fills**")
        st.dataframe(fills, hide_index=True, width="stretch")


def jobs_panel():
    q = RESULTS / "_jobs"
    rows = []
    for state in ("running", "queue", "done"):
        for f in sorted((q / state).glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if (q / state).exists() else []:
            j = json.loads(f.read_text())
            rep = q / f"{j['id']}.full.json"
            v = json.loads(rep.read_text())["verdict"] if rep.exists() else ""
            rows.append(dict(job=j["id"], state={"queue": "queued"}.get(state, state),
                             stage=j.get("stage", "") if state == "running" else "", status=j.get("status", ""),
                             verdict=v, strategy=j["strategy"].split("/")[-1], series=", ".join(j["series"]),
                             created=j["created"][:16].replace("T", " ")))
    if not rows:
        return
    with st.expander(f"Validation jobs ({sum(r['state'] != 'done' for r in rows)} active, {len(rows)} total)",
                     expanded=any(r["state"] != "done" for r in rows)):
        st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
        pick = st.selectbox("Job report", [r["job"] for r in rows])
        for stage in ("quick", "full"):
            rep = q / f"{pick}.{stage}.json"
            if rep.exists():
                r = json.loads(rep.read_text())
                label = f"**{stage}**" + (f" · verdict: **{r['verdict']}**" if stage == "full" else "")
                st.markdown(label)
                df = pd.DataFrame(r["cards"]).T.reset_index(names="run")
                st.dataframe(df, hide_index=True, width="stretch")
        log = q / f"{pick}.log"
        if log.exists():
            with st.expander("log"):
                st.code(log.read_text()[-5000:])
        st.caption("Each stage's runs are also in the Run selector below as <job>-<run>.")


def runs_page():
    st.title("Runs")
    jobs_panel()
    results_panel()


def pipeline_page():
    from kalshi_lab.dashboard.pipeline import page
    page(T, layout)


def new_backtest_page():
    run_panel()


nav = st.navigation([st.Page(pipeline_page, title="Strategies", default=True),
                     st.Page(runs_page, title="Runs"),
                     st.Page(new_backtest_page, title="New backtest")])
nav.run()
