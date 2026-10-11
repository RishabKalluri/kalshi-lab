"""H1 screen: does the Coinbase-vs-Binance premium predict the next 15-minute return? Development data only.
1-minute Coinbase closes vs Binance 1 s last price. Step 1 pins down candle alignment (corr of 1-min returns at
lags -2..+2). Step 2: at each window open T (every 15 min): prem(T) = log(cb/bn); features
  dev24 = prem(T) - mean prem over the previous 24 h, d15/d60 = prem(T) - prem(T-15/60 min);
target r = Binance log return T -> T+15m / trailing 60-min vol. Reports corr per feature, coin, half, and the hit rate
of sign(feature) == sign(r) in the top decile of |feature|."""
import json, os, sys
from pathlib import Path
import numpy as np, pandas as pd
from kalshi_lab.data.flow import load_flow
from kalshi_lab.recorder.sink import EXT, read_lines
from kalshi_lab.validate import LOCKBOX_START

BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
END = pd.Timestamp(LOCKBOX_START) - pd.Timedelta(days=1)


def coinbase(sym):
    rows = []
    for f in sorted((BF / "spot" / f"coinbase_{sym}usd").glob(f"*{EXT}")):
        if f.name[:10] < "2025-12-01" or f.name[:10] > END.strftime("%Y-%m-%d"):
            continue
        for line in read_lines(f):
            d = json.loads(line)
            rows.append((d["t"] // 10**9, d["m"]["price"]))
    s = pd.DataFrame(rows, columns=["t", "cb"]).drop_duplicates("t").set_index("t").cb
    return s


def binance_min(sym, shift=0):
    f = load_flow(f"binance_{sym}usdt", "2025-12-01", END.date())
    px = pd.Series(f.px.values, index=f.t.values)
    px = px[~px.index.duplicated()]
    full = px.reindex(np.arange(px.index[0], px.index[-1] + 1)).ffill()
    return full


if __name__ == "__main__":
    for sym in sys.argv[1:] or ["btc", "eth", "sol"]:
        cb = coinbase(sym)
        bn = binance_min(sym)
        t = cb.index.values
        t = t[(t >= bn.index[0] + 86400) & (t <= bn.index[-1] - 1000)]
        cbv = np.log(cb.loc[t].values)
        rc = np.diff(cbv)
        print(f"\n== {sym}: {len(t)} coinbase minutes")
        for lag in (-120, -60, 0, 60, 120):
            bv = np.log(bn.reindex(t + lag).values)
            print(f"  corr(cb 1-min ret, binance 1-min ret with Binance stamped t{lag:+d}s): {np.corrcoef(rc, np.diff(bv))[0,1]:.3f}")
        # choose best alignment
        best = max((-120, -60, 0, 60, 120), key=lambda L: np.corrcoef(rc, np.diff(np.log(bn.reindex(t + L).values)))[0, 1])
        print("  best alignment: binance at t%+d s" % best)
        prem = pd.Series(cbv - np.log(bn.reindex(t + best).values), index=t)
        prem = prem.reindex(np.arange(t[0], t[-1] + 1, 60)).ffill()
        opens = prem.index[(prem.index % 900 == 0)]
        opens = opens[(opens >= prem.index[0] + 86400) & (opens + 900 <= bn.index[-1])]
        p = prem
        df = pd.DataFrame(index=opens)
        df["prem"] = p.loc[opens].values
        roll = p.rolling(1440, min_periods=1000).mean()
        df["dev24"] = df.prem - roll.loc[opens].values
        df["d15"] = df.prem - p.reindex(opens - 900).values
        df["d60"] = df.prem - p.reindex(opens - 3600).values
        b0, b1 = bn.reindex(opens).values, bn.reindex(opens + 900).values
        lr = np.log(bn.values)
        c2 = np.concatenate([[0], np.cumsum(np.diff(lr) ** 2)])
        i = (opens - bn.index[0]).astype(int)
        vol = np.sqrt((c2[i] - c2[i - 3600]) / 3600 * 900)
        df["r"] = np.log(b1 / b0) / vol
        df["half"] = np.where(opens < pd.Timestamp("2026-05-01", tz="UTC").timestamp(), "A", "B")
        df = df.dropna()
        for feat in ("dev24", "d15", "d60"):
            out = []
            for h in "AB":
                x = df[df.half == h]
                top = x[x[feat].abs() >= x[feat].abs().quantile(0.9)]
                out.append(f"{h}: corr {np.corrcoef(x[feat], x.r)[0,1]:+.3f} top-decile hit {np.mean(np.sign(top[feat]) == np.sign(top.r)):.3f} (n {len(top)})")
            print(f"  {feat:6s} " + " | ".join(out))
        print("  premium bp: median %.1f, sd of d60 %.2f" % (1e4 * df.prem.median(), 1e4 * df.d60.std()))
