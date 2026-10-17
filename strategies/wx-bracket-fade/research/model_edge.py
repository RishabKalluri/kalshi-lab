import pandas as pd, numpy as np, sys
from scipy.stats import norm
sys.path.insert(0, "strategies/wx-bracket-fade/research")
from build_daily import daily, obs, LST
df = pd.read_parquet("strategies/wx-bracket-fade/research/snaps.parquet")
df["y"] = (df.result == "yes").astype(float)
fee = lambda p: 0.07 * p * (1 - p)
TRAIL, MINN = 60, 25

def fc_table(lead):
    rows = []
    for s in LST:
        f, o = daily(s), obs(s)
        for d in f[f"gfs_seamless:day{lead}"]:
            if f"ecmwf_ifs025:day{lead}" in f and d in f[f"ecmwf_ifs025:day{lead}"].keys():
                rows.append(dict(series=s, day=d, gfs=f[f"gfs_seamless:day{lead}"][d], ec=f[f"ecmwf_ifs025:day{lead}"][d], obs=o.get(d, np.nan)))
    t = pd.DataFrame(rows).sort_values(["series", "day"])
    return t

def add_model(t):
    out = []
    for s, g in t.groupby("series"):
        g = g.reset_index(drop=True)
        mu, sd = [], []
        for i in range(len(g)):
            h = g.iloc[max(0, i - TRAIL - 1): i - 1].dropna()  # target days strictly before d-1 (obs known by D-1)
            if len(h) < MINN: mu.append(np.nan); sd.append(np.nan); continue
            f = (g.gfs[i] + g.ec[i]) / 2
            hb = ((h.gfs + h.ec) / 2)
            b = (h.obs - hb).mean(); e = h.obs - hb - b
            mu.append(f + b); sd.append(max(1.5, e.std()))
        g["mu"], g["sd"] = mu, sd
        out.append(g)
    return pd.concat(out)

def prob(r):
    if r.stype == "between": lo, hi = r.floor - .5, r.cap + .5
    elif r.stype == "less": lo, hi = -1e9, r.cap - .5
    else: lo, hi = r.floor + .5, 1e9
    return norm.cdf((hi - r.mu) / r.sd) - norm.cdf((lo - r.mu) / r.sd)

if __name__ == "__main__":
    t1 = add_model(fc_table(1))
    d = df.merge(t1[["series", "day", "mu", "sd"]], on=["series", "day"])
    d = d[d.mu.notna() & (d.h >= 0)]
    d["pm"] = d.apply(prob, axis=1)
    d.to_parquet("strategies/wx-bracket-fade/research/snaps_model.parquet")
    print(len(d), "brier model", ((d.pm - d.y) ** 2).mean())
    mid = (d.ask + d.bid) / 2
    ok = d.ask.notna() & d.bid.notna()
    print("brier mid", ((mid[ok] - d.y[ok]) ** 2).mean(), "model same rows", ((d.pm[ok] - d.y[ok]) ** 2).mean())
    for margin in (0.03, .05, .08, .12):
        for hh in (0, 6):
            x = d[d.h == hh]
            # buy YES at ask when pm - ask > margin
            a = x[x.ask.notna() & (x.ask_age < 120) & (x.pm - x.ask > margin)].copy(); a["pnl"] = a.y - a.ask - fee(a.ask)
            n = x[x.bid.notna() & (x.bid_age < 120) & ((1 - x.pm) - (1 - x.bid) > margin)].copy(); n["pnl"] = (1 - n.y) - (1 - n.bid) - fee(1 - n.bid)
            print(margin, hh, "YES n=%d %.4f | NO n=%d %.4f" % (len(a), a.pnl.mean(), len(n), n.pnl.mean()))
