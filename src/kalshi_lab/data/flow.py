"""Load order-flow history written by `kalshi-lab backfill --only flow` (see data/backfill.py backfill_flow).

    from kalshi_lab.data.flow import load_flow, flow_sources
    flow_sources("KXETH15M")                 # {'binance': 'binance_ethusdt', 'okx': 'okx_ethusdtswap'}
    df = load_flow("okx_ethusdtswap", "2026-03-01", "2026-03-08")   # [start, end) dates, UTC
    dense = load_flow("binance_ethusdt", "2026-03-01", "2026-03-02", dense=True)

Columns: t (unix second; trades in (t-1, t]), px, buy, sell (taker volume in the base coin), n, max_trade.
Seconds without trades are absent unless dense=True (then volumes are 0 and px is carried forward).
Research only for now: the recorder doesn't stream these sources live, so a strategy can't use them in
paper/live trading until it does (ask the user).
"""

import os
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

from ..recorder.config import MARKETS

FLOW = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill" / "flow"


def flow_sources(series: str) -> dict[str, str]:
    src = MARKETS.get(series, {}).get("flow", {})
    return {ex: f"{ex}_{sym.replace('-', '').lower()}" for ex, sym in src.items()}


def load_flow(source: str, start: str | date, end: str | date, dense: bool = False) -> pd.DataFrame:
    start, end = date.fromisoformat(str(start)), date.fromisoformat(str(end))
    parts = []
    d = start
    while d < end:
        p = FLOW / source / f"{d.isoformat()}.parquet"
        if p.exists():
            parts.append(pd.read_parquet(p))
        d += timedelta(days=1)
    if not parts:
        return pd.DataFrame(columns=["t", "px", "buy", "sell", "n", "max_trade"])
    df = pd.concat(parts, ignore_index=True).sort_values("t", ignore_index=True)
    if dense:
        t = np.arange(df["t"].iloc[0], df["t"].iloc[-1] + 1)
        df = df.set_index("t").reindex(t)
        df[["buy", "sell", "n"]] = df[["buy", "sell", "n"]].fillna(0)
        df["px"] = df["px"].ffill()
        df = df.rename_axis("t").reset_index()
    return df
