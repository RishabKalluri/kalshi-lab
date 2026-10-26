"""NFL paper trading card for the Sports page: reads the nfl-q4 repo's paper logs on this server (no orders are ever placed).

  <date>_<slate>_trades.csv / _settled.csv   start-of-Q4 rule (nfl-q4 src/live/paper_trader.py; settle.py adds pnl)
  addon_tt_<date>.csv                        close-game team totals at Q3 post-score kickoffs (oos/paper_addon.py)
  addon_make_<date>.csv                      maker at fair -/+ 7c after Q3 scores; only filled orders count
Run daily by kalshi-nflpaper.timer (deploy/server_setup.sh).
"""

import os
import subprocess
from pathlib import Path

import numpy as np
import pandas as pd
import streamlit as st

PAPER = Path(os.environ.get("NFL_Q4_ROOT", "/srv/nfl-q4")) / "data" / "paper"
STRATS = {
    "q4": ("Start-of-Q4 rule", "The tested rule: the drive simulator vs Kalshi at the Q3 break and Q4 stoppages, "
                               "¼ Kelly, 2% per bet family, 5% per game, $1,000 paper bankroll."),
    "tt": ("Close-game team totals", "Team-total markets at kickoffs after Q3 scores when the score is within 8; "
                                     "EV 2-10¢ after fee; up to 10 contracts."),
    "make": ("Market-making after Q3 scores", "Resting 1 contract at the model price ± 7¢ for one minute; counts only when "
                                              "a public trade went through the price."),
}


def _read(f: Path) -> pd.DataFrame:
    try:
        return pd.read_csv(f)
    except (pd.errors.EmptyDataError, OSError):
        return pd.DataFrame()


@st.cache_data(ttl=120, show_spinner=False)
def load() -> pd.DataFrame:
    """One row per paper position: date, strategy, matchup, market, side, price, contracts, cost, pnl (NaN until settled)."""
    rows = []
    for f in sorted(PAPER.glob("*_trades.csv")):
        settled = f.with_name(f.name.replace("_trades.csv", "_settled.csv"))
        t = _read(settled if settled.exists() else f)
        if t.empty:
            continue
        rows.append(pd.DataFrame(dict(date=f.name[:10], strategy="q4", matchup=t.matchup, market=t.market, side=t.side,
                                      price=t.fill_price, contracts=t.contracts, cost=t.cost,
                                      pnl=t["pnl"] if "pnl" in t else np.nan)))
    for f in sorted(PAPER.glob("addon_tt_*.csv")):
        t = _read(f)
        if t.empty:
            continue
        pay = np.where(t.side == "YES", t.result, 1 - t.result)
        rows.append(pd.DataFrame(dict(date=f.stem[-10:], strategy="tt", matchup=t.matchup, market=t.market, side=t.side,
                                      price=t.price, contracts=t.contracts, cost=t.contracts * (t.price + t.fee),
                                      pnl=t.contracts * (pay - t.price - t.fee))))
    for f in sorted(PAPER.glob("addon_make_*.csv")):
        t = _read(f)
        if t.empty or "filled" not in t:
            continue
        t = t[t.filled.astype(str).str.lower() == "true"]
        if t.empty:
            continue
        bid = t.side == "BID"
        rows.append(pd.DataFrame(dict(date=f.stem[-10:], strategy="make", matchup=t.matchup, market=t.market,
                                      side=np.where(bid, "YES (bid)", "NO (offer)"), price=t.price, contracts=1,
                                      cost=np.where(bid, t.price, 1 - t.price),
                                      pnl=np.where(bid, t.result - t.price, t.price - t.result))))
    return pd.concat(rows, ignore_index=True) if rows else pd.DataFrame()


def _status() -> str:
    try:
        active = subprocess.run(["systemctl", "is-active", "kalshi-nflpaper"], capture_output=True, text=True).stdout.strip()
        nxt = subprocess.run(["systemctl", "show", "kalshi-nflpaper.timer", "-p", "NextElapseUSecRealtime", "--value"],
                             capture_output=True, text=True).stdout.strip()
    except OSError:
        return ""
    return "running today (waiting for or trading games)" if active == "active" else f"idle; next check {nxt or 'unknown'}"


def section():
    st.subheader("NFL paper trading")
    st.caption(f"nfl-q4 drive simulator · no orders are placed · {_status()}")
    t = load()
    rows = []
    for k, (name, what) in STRATS.items():
        s = t[t.strategy == k] if not t.empty else t
        done = s[s.pnl.notna()] if not s.empty else s
        n = int(done.contracts.sum()) if not done.empty else 0
        rows.append({"strategy": name, "game days": s.date.nunique() if not s.empty else 0,
                     "trades": len(s), "contracts": int(s.contracts.sum()) if not s.empty else 0,
                     "staked $": round(float(s.cost.sum()), 2) if not s.empty else 0.0,
                     "settled P&L $": round(float(done.pnl.sum()), 2) if not done.empty else 0.0,
                     "¢ / contract": round(100 * float(done.pnl.sum()) / n, 1) if n else None,
                     "awaiting settlement": int(len(s) - len(done)), "what it does": what})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    if t.empty:
        st.info("No NFL paper trades yet. They start at kickoffs after Q3 scores and at the end of Q3 on game days.")
        return
    with st.expander(f"All NFL paper trades ({len(t)})"):
        show = t.assign(strategy=t.strategy.map(lambda k: STRATS[k][0])).sort_values("date", ascending=False)
        st.dataframe(show.round({"price": 2, "cost": 2, "pnl": 2}), hide_index=True, width="stretch")
    st.caption("One game day is a tiny sample: judge these over weeks of Sundays.")
