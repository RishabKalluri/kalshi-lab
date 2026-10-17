"""Screening: per game-market pre-game trade stats (dev data only). Writes frame.parquet and trades.parquet."""
import sys, json
from pathlib import Path
import pandas as pd
sys.path.insert(0, "/srv/kalshi/src")
from kalshi_lab.recorder.sink import read_lines
from kalshi_lab.validate import LOCKBOX_START

OUT = Path(__file__).parent
sched = json.load(open("/srv/kalshi/strategies/longshot-fade/research/schedule.json"))
root = Path("/srv/kalshi-data/backfill/kalshi")
lb = LOCKBOX_START.strftime("%Y-%m-%d")
rows, tr = [], []
for s in ("KXNBAGAME", "KXNHLGAME"):
    for f in sorted(root.glob(f"{s}/*/*.jsonl.zst")):
        if f.parent.name >= lb or f.parent.name < "2026-01-07":
            continue
        lines = list(read_lines(f))
        if not lines:
            continue
        d0 = json.loads(lines[0])["m"]
        mk = d0.get("market", {})
        et = mk.get("event_ticker")
        if et not in sched:
            continue
        res = None
        for ln in lines:
            d = json.loads(ln)
            m = d["m"]
            if m.get("event") == "settled":
                res = m.get("market", {}).get("result") or m.get("result")
            elif m.get("type") == "trade":
                g = m["msg"]
                tr.append((mk["ticker"], d["t"], float(g["yes_price_dollars"]), float(g["count_fp"]), g["taker_side"]))
        rows.append(dict(ticker=mk["ticker"], event=et, series=s, start=sched[et]["start"], end=sched[et]["end"],
                         exp=mk.get("expected_expiration_time"), result=res, open=mk.get("open_time"),
                         close=mk.get("close_time")))
pd.DataFrame(rows).to_parquet(OUT / "frame.parquet")
pd.DataFrame(tr, columns=["ticker", "t", "p", "n", "side"]).to_parquet(OUT / "trades.parquet")
print(len(rows), len(tr))
