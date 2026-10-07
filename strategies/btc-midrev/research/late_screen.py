"""H1/H2 screen on KXBTC15M: late-confirmed fade (BTC-only) and the market-wide basket version. Dev data only.

    uv run python strategies/btc-midrev/research/late_screen.py

As eth-midrev/research/late_move.py: rows h in 870..780, mid 30-70c, fresh quotes (age <= 120 s), first trigger per
market, fade at the next real fill (next taker print within 10 s) after the taker fee. Halves A (< May 1) / B.
zL(coin) = (A(open) - A(open - L)) / (rv_60m(coin) * sqrt(L)), A = 60 s Binance average ending at t; rv_60m from 1 s
price changes over the hour before the open. Basket Z = mean of BTC, ETH, SOL z.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "eth-overreact/research"))
from panel import load_spot  # noqa: E402

ROOT = Path(__file__).resolve().parents[3]
MAY = int(pd.Timestamp("2026-05-01", tz="UTC").timestamp())
fee = lambda p: 0.07 * p * (1 - p)
SERIES = sys.argv[1] if len(sys.argv) > 1 else "KXBTC15M"
own = SERIES[2:5].lower()
d = pd.read_parquet(ROOT / f"research/data/eth-overreact/{SERIES}_panel.parquet")
d = d[d.h >= 780]
op = d.close.to_numpy().astype(int) - 900
for coin in ("btc", "eth", "sol"):
    T0, s = load_spot(f"binance_{coin}usdt")
    cs = np.concatenate([[0.0], np.cumsum(s)])
    c2 = np.concatenate([[0.0], np.cumsum(np.concatenate([[0.0], np.diff(s) ** 2]))])
    ok = (op - 3700 - T0 >= 0) & (op - T0 < len(s))
    i = np.clip(op - T0, 3700, len(s) - 1)
    avg = lambda j: (cs[j] - cs[j - 60]) / 60
    rv = np.sqrt((c2[i] - c2[i - 3600]) / 3600)
    for L in (300, 900):
        d[f"{coin}_z{L}"] = np.where(ok, (avg(i) - avg(i - L)) / (rv * np.sqrt(L)), np.nan)
d["B15"] = d[[f"{own}_z900", "eth_z900", "sol_z900"]].mean(axis=1, skipna=False)
d["B5"] = d[["btc_z300", "eth_z300", "sol_z300"]].mean(axis=1, skipna=False)
d["mid"] = (d.ask + d.bid) / 2
d["half"] = np.where(d.close < MAY, "A", "B")
d["mon"] = pd.to_datetime(d.close, unit="s").dt.strftime("%m")
d = d[(d.h >= 780) & d.mid.between(0.3, 0.7) & (d.age_ask <= 120) & (d.age_bid <= 120)]
sg = np.sign


def report(mask, col, lab):
    e = d[mask].copy()
    up = e[col] < 0
    e["pnl"] = np.where(up, e.y - e.next_ask - fee(e.next_ask), e.next_bid - e.y - fee(e.next_bid))
    e = e.dropna(subset=["pnl"]).sort_values("h", ascending=False).groupby("ticker").head(1)
    g = e.groupby("half").pnl.agg(c=lambda x: 100 * x.mean(), se=lambda x: 100 * x.std() / np.sqrt(len(x)), n="size")
    mo = e.groupby("mon").pnl.mean().mul(100).round(1).to_dict()
    row = "  ".join(f"{h} {g.loc[h,'c']:+.2f} (se {g.loc[h,'se']:.2f}, n {int(g.loc[h,'n'])})" for h in g.index)
    print(f"{lab:46s} {row}  months {mo}")
    return e


bz15, bz5 = d[f"{own}_z900"], d[f"{own}_z300"]
late = (bz15.abs() > 1.5) & (bz5.abs() > 1.5) & (sg(bz5) == sg(bz15))
basket = (d.B15.abs() > 1.5) & (d.B5.abs() > 1.5) & (sg(d.B5) == sg(d.B15)) & (sg(bz15) == sg(d.B15))
print(f"== {SERIES}, first trigger per market, fade at next fill after fee, c/contract")
report(bz15.abs() > 1.5, f"{own}_z900", "eth-overreact rule |z15|>1.5 (control)")
report(late, f"{own}_z900", "H1 late-confirmed (BTC-only signal)")
report((bz15.abs() > 1.5) & ~late, f"{own}_z900", "|z15|>1.5 NOT late-confirmed")
report(basket, f"{own}_z900", "H2 basket late-confirmed")
report(late & basket, f"{own}_z900", "H1 & H2 (both)")
report(late & ~basket, f"{own}_z900", "H1 without basket (BTC-only burst)")
report(basket & ~late, f"{own}_z900", "H2 without BTC late-confirmed")
