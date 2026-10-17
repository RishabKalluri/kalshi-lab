"""Per NHL game: ESPN-derived intermission windows relative to the expected_expiration-based start estimate."""
import sys, json
from pathlib import Path
import numpy as np, pandas as pd
sys.path.insert(0, "/srv/kalshi/research")
import sports_breaks as sb
D = sys.argv[1]
df = pd.read_parquet(f"{D}/KXNHLGAME.parquet", columns=["event", "exp_ns", "market"]).drop_duplicates("event")
espn = sb.Espn(Path("/srv/kalshi/research/data/espn"), 0.7)
import zstandard
rows = []
for _, r in df.iterrows():
    ev = r.event
    f = next(iter(Path("/srv/kalshi-data/backfill/kalshi/KXNHLGAME").glob(f"*/{r.market}.jsonl.zst")))
    sett = None
    for line in zstandard.ZstdDecompressor().decompress(f.read_bytes(), max_output_size=2**31).splitlines():
        if b'"settled"' in line[:80] or b'"event": "settled"' in line:
            sett = json.loads(line)["m"]["market"]
    if sett is None: continue
    text = " ".join(str(sett.get(k, "")) for k in ("title", "rules_primary", "yes_sub_title", "no_sub_title"))
    g = sb.match_game(espn, "hockey/nhl", ev, text)
    if not g: continue
    sm = espn.summary("hockey/nhl", g["id"])
    tl = sb.timeline(sm, "hockey") if sm else None
    if not tl: continue
    est = r.exp_ns - 171 * 60 * 10**9
    ints = [(a, b) for a, b, ph, sub in tl["segs"] if sub == "halftime"]
    rows.append(dict(event=ev, est=est, espn_start=tl["start"], end=tl["end"], ints=ints))
out = pd.DataFrame(rows)
out.to_pickle(sys.argv[1] + "/nhl_windows.pkl")
m = 60 * 10**9
print(len(out), "games")
print("espn start - est start (min):", np.percentile((out.espn_start - out.est) / m, [5, 25, 50, 75, 95]).round(1))
print("game length (min):", np.percentile((out.end - out.espn_start) / m, [5, 25, 50, 75, 95]).round(1))
for i in (0, 1):
    a = [(x[i][0] - e) / m for x, e in zip(out.ints, out.est) if len(x) > i]
    d = [(x[i][1] - x[i][0]) / m for x in out.ints if len(x) > i]
    print(f"intermission {i+1}: start rel est (min) pct5-95", np.percentile(a, [5, 25, 50, 75, 95]).round(1), "dur", np.percentile(d, [5, 50, 95]).round(1), len(a))
