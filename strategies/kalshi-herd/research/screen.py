"""H1 screen: does net Kalshi taker flow over the last W seconds predict outcome minus price? Dev data only.
For each research-dataset row (market x checkpoint h, mid 15-85c): imb = (YES-taker qty - NO-taker qty) / total over
(t-W, t], from settle-lockin's trade dumps. Reports corr(imb, y - mid), and by imb quintile the PnL of FADING the flow
(buy the side the takers sold) at the next real fill after the fee, halves A/B. Also a residual version: imb
orthogonalised to the spot-model change of probability over the same W (approximated by the mid change)."""
import sys
from pathlib import Path
import numpy as np, pandas as pd
from kalshi_lab.validate import LOCKBOX_START

ROOT = Path(__file__).resolve().parents[3]


def panel(s, W):
    d = pd.read_parquet(ROOT / f"research/data/{s}.parquet")
    d = d[d.close < pd.Timestamp(LOCKBOX_START)].copy()
    d["close_s"] = ((d.close - pd.Timestamp("1970-01-01", tz="UTC")).dt.total_seconds()).astype("int64")
    tr = pd.read_parquet(ROOT / f"research/data/settle-lockin/{s}_trades.parquet")
    tr = tr.sort_values("t")
    tr["sq"] = np.where(tr.buy, tr.qty, -tr.qty)
    out = []
    for tk, g in tr.groupby("ticker", observed=True):
        rows = d[d.ticker == tk]
        if rows.empty:
            continue
        t = g.t.values
        cs, ca = np.concatenate([[0], np.cumsum(g.sq.values)]), np.concatenate([[0], np.cumsum(g.qty.values)])
        now = (rows.close_s - rows.h).values
        i1 = np.searchsorted(t, now, side="right")
        i0 = np.searchsorted(t, now - W, side="right")
        out.append(pd.DataFrame({"idx": rows.index, "sflow": cs[i1] - cs[i0], "vol": ca[i1] - ca[i0], "ntr": i1 - i0}))
    f = pd.concat(out).set_index("idx")
    d = d.join(f, how="inner")
    d["imb"] = d.sflow / d.vol.where(d.vol > 0)
    d["half"] = np.where(d.close < pd.Timestamp("2026-05-01", tz="UTC"), "A", "B")
    return d


if __name__ == "__main__":
    W = int(sys.argv[1]) if len(sys.argv) > 1 else 180
    fee = lambda p: 7 * p * (1 - p)
    for s in ["KXETH15M", "KXSOL15M", "KXBTC15M"]:
        d = panel(s, W)
        x = d[d.mid.between(0.15, 0.85) & (d.ntr >= 3) & d.imb.notna()].copy()
        # fade: imb > 0 (YES bought) -> buy NO at 1 - next_bid; imb < 0 -> buy YES at next_ask
        px = np.where(x.imb > 0, 1 - x.next_bid, x.next_ask)
        win = np.where(x.imb > 0, 1 - x.y, x.y)
        x["fade"] = 100 * (win - px) - fee(px)
        x = x[np.isfinite(x.fade)]
        x["q"] = pd.qcut(x.imb.abs(), 5, labels=False, duplicates="drop")
        print(f"\n== {s} W={W}s  rows {len(x)}  corr(imb, y-mid) A {x[x.half=='A'][['imb']].assign(r=x.y-x.mid).corr().iloc[0,1]:.3f}"
              f" B {x[x.half=='B'][['imb']].assign(r=x.y-x.mid).corr().iloc[0,1]:.3f}")
        print(x.groupby(["q", "half"]).agg(absimb=("imb", lambda v: v.abs().mean()), fade=("fade", "mean"),
                                           n=("fade", "size")).unstack("half").round(2).to_string())
        # strongest: |imb| > 0.8 and many trades
        y = x[(x.imb.abs() > 0.8) & (x.ntr >= 8)]
        print("  |imb|>0.8 & ntr>=8: fade A %.2f B %.2f (n %d/%d)" % (y[y.half == 'A'].fade.mean(), y[y.half == 'B'].fade.mean(),
                                                                    (y.half == 'A').sum(), (y.half == 'B').sum()))
