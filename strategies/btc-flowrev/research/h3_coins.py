"""H3 corroboration: 16:00 ET session-return reversal on ETH/SOL spot (not used for tuning). Dev only."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "strategies/eth-overreact/research"))
from panel import load_spot  # noqa: E402
MAY = int(pd.Timestamp("2026-05-01", tz="UTC").timestamp())
HOL = {"2025-11-27", "2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03"}
for coin in ("btc", "eth", "sol"):
    T0, s = load_spot(f"binance_{coin}usdt")
    cs = np.concatenate([[0.0], np.cumsum(s)]); ls = np.log(s)
    c2 = np.concatenate([[0.0], np.cumsum(np.concatenate([[0.0], np.diff(ls) ** 2]))])
    avg = lambda j: (cs[j] - cs[j - 60]) / 60
    days = pd.date_range(pd.Timestamp(T0 + 86400, unit="s", tz="UTC").tz_convert("America/New_York").normalize(),
                         pd.Timestamp(T0 + len(s) - 3000, unit="s", tz="UTC").tz_convert("America/New_York").normalize(), freq="D")
    rows = []
    for d in days:
        o = int((d + pd.Timedelta(hours=16)).timestamp()); a = int((d + pd.Timedelta(hours=9, minutes=30)).timestamp())
        i, j = o - T0, a - T0
        if i + 960 >= len(s) or j < 3700:
            continue
        rv = np.sqrt((c2[i] - c2[i - 3600]) / 3600)
        R = np.log(s[i] / s[j]) / (rv * np.sqrt(i - j))
        z = np.log(avg(i + 900) / avg(i)) / (rv * 30)
        rows.append((o, d.weekday() < 5 and d.strftime("%Y-%m-%d") not in HOL, R, z))
    x = pd.DataFrame(rows, columns=["o", "trading", "R", "z"]); x["half"] = np.where(x.o < MAY, "A", "B")
    g = x.groupby(["trading", "half"]).apply(lambda q: f"{q.R.corr(q.z):+.2f} (n {len(q)})").unstack()
    print(coin, g.to_dict("index"))
