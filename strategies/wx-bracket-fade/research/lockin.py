"""Intraday: running METAR max vs bracket prices. Snapshot at LST hours H on target day D."""
import json, sys
import pandas as pd, numpy as np
from pathlib import Path
from datetime import datetime, timezone, timedelta
sys.path.insert(0, str(Path(__file__).parent))
from build_daily import LST
import build_snaps as bs
D = Path(__file__).resolve().parent.parent / "data"
HRS = [10, 12, 14, 16, 18, 20, 22]
def metar_max(series):
    m = pd.read_csv(D / f"metar_{series}.csv", parse_dates=["valid"]); m = m[m.tmpf.notna()]
    m["t"] = m.valid.dt.tz_localize("UTC").dt.as_unit("s").astype("int64")
    return m[["t", "tmpf"]].sort_values("t").to_numpy()
def one(args):
    series, path = args
    meta, trades, res = bs.parse(path)
    if meta is None or res is None or not res.get("result"): return []
    ev = meta["event_ticker"].split("-")[1]
    day = datetime(2000 + int(ev[:2]), bs.MON[ev[2:5]], int(ev[5:]))
    mid = day.replace(tzinfo=timezone.utc).timestamp() - LST[series] * 3600
    mm = MM[series]; rows = []
    for h in HRS:
        t0 = mid + h * 3600
        sel = mm[(mm[:, 0] > mid) & (mm[:, 0] <= t0 - 600)]  # METAR reaches us ~10 min after valid
        if len(sel) == 0: continue
        M = sel[:, 1].max()
        ask = bid = None; ask_t = bid_t = 0
        for (t, p, q, buy) in trades:
            if t > t0: break
            if buy:
                ask, ask_t = p, t
                if bid is not None and bid >= p: bid = None
            else:
                bid, bid_t = p, t
                if ask is not None and ask <= p: ask = None
        rows.append(dict(series=series, ticker=meta["ticker"], day=day.date().isoformat(), stype=meta["strike_type"], floor=meta.get("floor_strike"),
                         cap=meta.get("cap_strike"), y=float(res["result"] == "yes"), h=h, M=M, ask=ask, bid=bid,
                         ask_age=(t0 - ask_t) / 60 if ask else None, bid_age=(t0 - bid_t) / 60 if bid else None))
    return rows
MM = {}
if __name__ == "__main__":
    import os
    from multiprocessing import Pool
    MM.update({s: metar_max(s) for s in LST})
    jobs = [(s, bs.ROOT / s / d / f) for s in LST for d in sorted(os.listdir(bs.ROOT / s)) if d < bs.LOCKBOX and not d.startswith("_")
            for f in os.listdir(bs.ROOT / s / d) if f.endswith(".zst")]
    with Pool(8) as p:
        out = [r for rows in p.imap_unordered(one, jobs, chunksize=20) for r in rows]
    pd.DataFrame(out).to_parquet(Path(__file__).parent / "intraday.parquet"); print(len(out))
