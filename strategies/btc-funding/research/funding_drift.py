"""H1 screen: BTC spot drift around the 8-hourly perp funding settlement (00/08/16 UTC). Dev data only.

    uv run python strategies/btc-funding/research/funding_drift.py [coin]

For each day and each full hour H: premium = mean over [H-60m, H-15m) of OKX perp / Binance spot - 1 (raw, and
demeaned by its trailing 7-day median). z_pre = log S(H)/S(H-15m) / (rv_60m*30), z_post = log S(H+15m)/S(H) / same,
rv_60m from 1 s Binance returns over [H-75m, H-15m). Report mean z (unconditional) and mean z*sign(premium) for
funding hours vs the rest, by half (A: < May 1, B: May 1 .. lockbox).
"""
import sys
import numpy as np
import pandas as pd
from kalshi_lab.data.flow import load_flow
from kalshi_lab.validate import LOCKBOX_START

coin = sys.argv[1] if len(sys.argv) > 1 else "btc"
END = LOCKBOX_START.strftime("%Y-%m-%d")
sp = load_flow(f"binance_{coin}usdt", "2025-12-01", END, dense=True)
pp = load_flow(f"okx_{coin}usdtswap", "2025-12-01", END, dense=True)
t0 = int(max(sp.t.iloc[0], pp.t.iloc[0])); t1 = int(min(sp.t.iloc[-1], pp.t.iloc[-1]))
S = sp.set_index("t").px.reindex(np.arange(t0, t1 + 1)).ffill().to_numpy()
P = pp.set_index("t").px.reindex(np.arange(t0, t1 + 1)).ffill().to_numpy()
lr = np.log(S)
r2 = np.concatenate([[0.0], np.diff(lr) ** 2]); cr2 = np.cumsum(r2)
prem = P / S - 1; cp = np.concatenate([[0.0], np.cumsum(np.nan_to_num(prem))])
LB = int(LOCKBOX_START.timestamp()); MAY = int(pd.Timestamp("2026-05-01", tz="UTC").timestamp())
Hs = np.arange((t0 // 3600 + 2) * 3600, min(t1, LB) - 3600, 3600)
i = Hs - t0
rv = np.sqrt((cr2[i - 900] - cr2[i - 4500]) / 3600) * 30
d = pd.DataFrame({"H": Hs, "hour": (Hs // 3600) % 24,
                  "prem": (cp[i - 900] - cp[i - 3600]) / 2700,
                  "z_pre": (lr[i] - lr[i - 900]) / rv, "z_post": (lr[i + 900] - lr[i]) / rv,
                  "z_pre2": (lr[i - 900] - lr[i - 1800]) / rv})
d = d[np.isfinite(d.z_pre) & np.isfinite(d.z_post) & (rv > 0)]
d["prem_dm"] = d.prem - d.prem.rolling(168, min_periods=48).median().shift(1)
d["half"] = np.where(d.H < MAY, "A", "B")
d["fund"] = d.hour.isin([0, 8, 16])
print(f"{coin}: {len(d)} hours, premium bp mean {1e4*d.prem.mean():+.2f} sd {1e4*d.prem.std():.2f}")
def tab(col):
    out = []
    for (f, h), g in d.groupby(["fund", "half"]):
        for sig in ("prem", "prem_dm"):
            s = np.sign(g[sig])
            x = g[col] * s
            out.append((("fund" if f else "other"), h, sig, len(x), x.mean(), x.std() / np.sqrt(x.notna().sum())))
        out.append((("fund" if f else "other"), h, "uncond", len(g), g[col].mean(), g[col].std() / np.sqrt(len(g))))
    return pd.DataFrame(out, columns=["hours", "half", "sign", "n", "mean_z", "se"]).round(3)
for col in ("z_pre2", "z_pre", "z_post"):
    print(f"--- {col}  (z in 15-min sigma units; signed by sign(premium))"); print(tab(col).to_string(index=False))
print("--- per funding hour, z_pre / z_post signed by prem, halves")
for hr in (0, 8, 16):
    g = d[d.hour == hr]
    for h, gg in g.groupby("half"):
        s = np.sign(gg.prem)
        print(hr, h, len(gg), "pre %+.3f post %+.3f | uncond pre %+.3f post %+.3f" % ((gg.z_pre*s).mean(), (gg.z_post*s).mean(), gg.z_pre.mean(), gg.z_post.mean()))
print("--- per hour (all), uncond z_pre / z_post")
print(d.groupby("hour")[["z_pre", "z_post"]].mean().round(3).T.to_string())
print("--- vol: mean z^2 by hour (1.0 = window moves like the trailing hour), halves")
v = d.assign(pre2=d.z_pre**2, post2=d.z_post**2).groupby(["half", "hour"])[["pre2", "post2"]].mean().round(2)
print(v.unstack(0).T.to_string())
