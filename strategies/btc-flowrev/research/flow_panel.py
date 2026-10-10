"""Build a checkpoint panel of Kalshi flow features for KXBTC15M (dev data only).
One row per (market, h): VWAP last 10 s, VWAP 60-70 s earlier, signed taker flow last 60 s / 10 s,
next taker-buy and taker-sell trade prices within 15 s after h (+0.3 s latency).
    uv run python strategies/btc-flowrev/research/flow_panel.py"""
import sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np, pandas as pd, pyarrow.parquet as pq

ROOT = Path(__file__).resolve().parents[3]
SRC = ROOT / "research/data/settle-lockin/KXBTC15M_trades.parquet"
OUT = ROOT / "research/data/btc-flowrev"
H = [780, 660, 540, 420, 300, 180, 120, 60]


def part(i):
    df = pq.ParquetFile(SRC).read_row_group(i, columns=["close", "t", "price", "buy", "qty"]).to_pandas()
    s = df.close.values - df.t.values
    out = []
    for h in H:
        m = (s > h - 15) & (s <= h + 70)
        d = df[m].copy()
        if d.empty:
            continue
        d["s"] = s[m]
        sg = np.where(d.buy, 1.0, -1.0) * d.qty
        d["pq"] = d.price * d.qty
        g = d.groupby("close")
        now = d[(d.s > h) & (d.s <= h + 10)].groupby("close")[["pq", "qty"]].sum()
        prev = d[(d.s > h + 60) & (d.s <= h + 70)].groupby("close")[["pq", "qty"]].sum()
        d["sg"] = sg
        f60 = d[(d.s > h) & (d.s <= h + 60)].groupby("close").agg(f60=("sg", "sum"), v60=("qty", "sum"), n60=("sg", "size"))
        f10 = d[(d.s > h) & (d.s <= h + 10)].groupby("close").agg(f10=("sg", "sum"))
        last = d[d.s > h].sort_values("t").groupby("close").agg(last=("price", "last"), last_t=("t", "last"))
        aft = d[(d.s <= h - 0.3)].sort_values("t")
        nb = aft[aft.buy].groupby("close").agg(nb=("price", "first"), nb_t=("t", "first"))
        ns = aft[~aft.buy].groupby("close").agg(ns=("price", "first"), ns_t=("t", "first"))
        r = pd.concat([now.add_suffix("_now"), prev.add_suffix("_prev"), f60, f10, last, nb, ns], axis=1)
        r["h"] = h
        out.append(r.reset_index())
    return pd.concat(out) if out else None


def first(x, tcol):
    return x


if __name__ == "__main__":
    n = pq.ParquetFile(SRC).metadata.num_row_groups
    with Pool(7) as pool:
        parts = [p for p in pool.map(part, range(n)) if p is not None]
    df = pd.concat(parts, ignore_index=True)
    # combine partials of markets split across row groups
    agg = df.groupby(["close", "h"]).agg(
        pq_now=("pq_now", "sum"), qty_now=("qty_now", "sum"), pq_prev=("pq_prev", "sum"), qty_prev=("qty_prev", "sum"),
        f60=("f60", "sum"), v60=("v60", "sum"), n60=("n60", "sum"), f10=("f10", "sum"))
    def pick(col, tcol, how):
        x = df.dropna(subset=[col]).sort_values(tcol)
        return x.groupby(["close", "h"])[col].agg(how)
    agg["last"] = pick("last", "last_t", "last")
    agg["nb"] = pick("nb", "nb_t", "first")
    agg["ns"] = pick("ns", "ns_t", "first")
    agg["nb_dt"] = df.dropna(subset=["nb"]).sort_values("nb_t").groupby(["close", "h"]).nb_t.first()
    agg["ns_dt"] = df.dropna(subset=["ns"]).sort_values("ns_t").groupby(["close", "h"]).ns_t.first()
    agg = agg.reset_index()
    agg["nb_dt"] -= agg.close - agg.h
    agg["ns_dt"] -= agg.close - agg.h
    agg["vw_now"] = agg.pq_now / agg.qty_now.replace(0, np.nan)
    agg["vw_prev"] = agg.pq_prev / agg.qty_prev.replace(0, np.nan)
    OUT.mkdir(exist_ok=True)
    agg.to_parquet(OUT / "flow_panel.parquet")
    print(len(agg), "rows", agg.close.nunique(), "markets")
