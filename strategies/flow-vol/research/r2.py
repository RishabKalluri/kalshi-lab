"""Does flow add OOS R2 to log rv_fut beyond HAR(+hour,+h)? Train Dec-Apr, test May-Aug; and monthly expanding."""
import sys, numpy as np, pandas as pd
pd.set_option("display.width", 200)


def load(series):
    d = pd.read_parquet(f"research/data/{series}.parquet")
    d = d[d.close < "2026-08-20"].reset_index(drop=True)
    f = pd.read_parquet(f"strategies/flow-vol/research/feats_{series}.parquet")
    assert (f.ticker.values == d.ticker.values).all() and (f.h.values == d.h.values).all()
    d = pd.concat([d, f.drop(columns=["ticker", "close", "h"])], axis=1)
    d = d[(d.rv_5m > 0) & (d.rv_15m > 0) & (d.rv_60m > 0) & (d.rv_4h > 0) & (d.rv_fut > 0)].copy()
    d["hour"] = d.close.dt.hour
    return d


def HAR(d):
    return np.column_stack([np.ones(len(d)), np.log(d.rv_15m), np.log(d.rv_60m), np.log(d.rv_4h),
                            *[(d.hour == hh).astype(float) for hh in range(1, 24)], np.log(d.h)])


GROUPS = {
    "vol": ["lv_1m", "lv_5m", "lv_15m", "lv_60m"],
    "trades": ["ln_1m", "ln_5m", "ln_15m", "ln_60m"],
    "max": ["lmx_60", "lmx_300"],
    "mix": ["perp_5m", "perp_15m", "aimb_5m", "aimb_15m", "simb_5m"],
}


def r2(y, p, base):
    return 1 - ((y - p) ** 2).sum() / ((y - base) ** 2).sum()


def fitpred(tr, te, cols):
    X = lambda x: np.column_stack([HAR(x)] + [x[c].to_numpy() for c in cols]) if cols else HAR(x)
    y = np.log(tr.rv_fut)
    b, *_ = np.linalg.lstsq(X(tr), y, rcond=None)
    return X(te) @ b


if __name__ == "__main__":
    for series in sys.argv[1:]:
        d = load(series)
        d = d[d.h.isin([60, 90, 120, 180, 240, 300, 360])]
        tr, te = d[d.close < "2026-05-01"], d[d.close >= "2026-05-01"]
        y = np.log(te.rv_fut); base = np.log(tr.rv_fut).mean()
        res = {"HAR": r2(y, fitpred(tr, te, []), base)}
        for g, c in GROUPS.items():
            res["+" + g] = r2(y, fitpred(tr, te, c), base)
        allc = sum(GROUPS.values(), [])
        res["+all"] = r2(y, fitpred(tr, te, allc), base)
        # HAR + rv_5m (is it flow or just the 5m rv?)
        d["l5"] = np.log(d.rv_5m); tr, te = d[d.close < "2026-05-01"], d[d.close >= "2026-05-01"]
        res["+rv5"] = r2(y, fitpred(tr, te, ["l5"]), base)
        res["+rv5+all"] = r2(y, fitpred(tr, te, ["l5"] + allc), base)
        print(series, len(tr), len(te)); print(pd.Series(res).round(4).to_string())
        # by-month expanding
        rows = []
        for m in pd.period_range("2026-03", "2026-08", freq="M"):
            a = d[d.close < m.start_time.tz_localize("UTC")]; b = d[(d.close >= m.start_time.tz_localize("UTC")) & (d.close < (m + 1).start_time.tz_localize("UTC"))]
            yb = np.log(b.rv_fut); bs = np.log(a.rv_fut).mean()
            rows.append((str(m), r2(yb, fitpred(a, b, []), bs), r2(yb, fitpred(a, b, allc), bs)))
        print(pd.DataFrame(rows, columns=["month", "HAR", "HAR+flow"]).round(4).to_string(index=False))
