"""Compare an ad-hoc engine run's traded markets with the research rule (late-confirmed fade) on the same dates.

    uv run python strategies/eth-midrev/research/check_engine.py results/<run> START END
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

run, start, end = sys.argv[1], sys.argv[2], sys.argv[3]
sys.argv = [sys.argv[0], "KXETH15M"]
src = (Path(__file__).parent / "late_move.py").read_text().split('print(f"== {series}')[0]
exec(compile(src.replace("Path(__file__)", f"Path({str(Path(__file__).resolve())!r})"), "late_move", "exec"))
m = (d.z900.abs() > 1.5) & (d.z300.abs() > 1.5) & (np.sign(d.z300) == np.sign(d.z900))
e = d[m].copy()
e["pnl"] = fade(e, "z900")
e = e.dropna(subset=["pnl"]).sort_values("h", ascending=False).groupby("ticker").head(1)
lo, hi = pd.Timestamp(start, tz="UTC").timestamp(), pd.Timestamp(end, tz="UTC").timestamp()
e = e[(e.close > lo) & (e.close <= hi)]
g = pd.read_csv(Path(run) / "markets.csv")
g = g[g.fills > 0]
r, t = set(e.ticker), set(g.ticker)
print(f"research {len(r)} markets {100 * e.pnl.mean():+.2f}c | engine {len(t)} | both {len(r & t)} | "
      f"research only {sorted(r - t)[:8]} | engine only {sorted(t - r)[:8]}")
