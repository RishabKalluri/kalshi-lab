"""Daily forecast highs (F) per city-day from hourly forecasts, in local standard time (NWS climate day)."""
import json, csv, sys
from pathlib import Path
from datetime import datetime, timedelta
import numpy as np
D = Path(__file__).resolve().parent.parent / "data"
LST = {"KXHIGHNY": -5, "KXHIGHLAX": -8, "KXHIGHMIA": -5, "KXHIGHCHI": -6, "KXHIGHAUS": -6, "KXHIGHTDAL": -6,
       "KXHIGHTPHX": -7, "KXHIGHTHOU": -6, "KXHIGHTATL": -5, "KXHIGHTBOS": -5}

def daily(series):
    j = json.loads((D / f"fc_{series}.json").read_text())
    t = [datetime.fromisoformat(x) for x in j["time"]]
    off = timedelta(hours=LST[series])
    days = [(x + off).date().isoformat() for x in t]
    out = {}
    for k, v in j.items():
        if k == "time": continue
        a = np.array([np.nan if x is None else x for x in v]) * 9 / 5 + 32
        d = {}
        for day, x in zip(days, a):
            d.setdefault(day, []).append(x)
        out[k] = {day: float(np.max(xs)) for day, xs in d.items() if len(xs) == 24 and not np.isnan(xs).any()}
    return out

def obs(series):
    r = {}
    for row in csv.DictReader(open(D / f"obs_{series}.csv")):
        if row["max_temp_f"]: r[row["day"]] = float(row["max_temp_f"])
    return r

if __name__ == "__main__":
    for s in LST:
        f, o = daily(s), obs(s)
        for k in f:
            days = sorted(set(f[k]) & set(o))
            e = np.array([o[d] - f[k][d] for d in days])
            print(s, k, len(days), "bias %.2f sd %.2f mae %.2f" % (e.mean(), e.std(), np.abs(e).mean()))
