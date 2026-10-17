"""Per-fill PnL vs settlement by side and price band, clustered by city-day. usage: research_fills.py <run dir>"""
import sys, re, collections
import pandas as pd
f = pd.concat([pd.read_csv(f"{d}/fills.csv") for d in sys.argv[1:]]); m = pd.concat([pd.read_csv(f"{d}/markets.csv") for d in sys.argv[1:]])
res = dict(zip(m.ticker, m.result))
f["yes"] = f.ticker.map(res).eq("yes")
f["sgn"] = f.side.map({"buy": 1, "sell": -1})
f["pnl"] = f.sgn * (f.yes.astype(float) * 1000 - f.price) / 10 * f.qty - f.fee * 100  # cents
f["band"] = pd.cut(f.price / 10, [0, 5, 10, 20, 30, 40, 50, 100])
f["cd"] = f.ticker.str.extract(r"^(KX\w+-\d\d[A-Z]{3}\d\d)")
f["t"] = pd.to_datetime(f.time)
for k in ("side", "band"):
    g = f.groupby(k, observed=True).apply(lambda x: pd.Series({"qty": x.qty.sum(), "pnl_c": x.pnl.sum(), "c_per_ct": x.pnl.sum() / x.qty.sum()}))
    print(g)
print(f.groupby(["side", "band"], observed=True).apply(lambda x: pd.Series({"qty": x.qty.sum(), "c_per_ct": x.pnl.sum() / x.qty.sum()})))
cd = f.groupby("cd").pnl.sum() / 100
print("city-days", len(cd), "mean $", cd.mean(), "se", cd.std() / len(cd) ** .5)
