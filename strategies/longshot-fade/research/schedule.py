"""Build schedule.json: event_ticker -> {start, end, sport} (ns) from ESPN cache, pre-lockbox settled markets only."""
import sys, json
from pathlib import Path
sys.path.insert(0, "/srv/kalshi/research")
import sports_breaks as sb
root = Path("/srv/kalshi-data/backfill/kalshi")
espn = sb.Espn(Path("/srv/kalshi/research/data/espn"), 0.15)
lb = sb.lockbox_start().strftime("%Y-%m-%d")
out, miss, tot = {}, 0, 0
for s in ("KXNBAGAME", "KXNHLGAME"):
    league, sport = sb.LEAGUE[s]
    seen = set()
    for f in sorted(root.glob(f"{s}/*/*.jsonl.zst")):
        if f.parent.name >= lb: continue
        r = sb.load(f)
        if not r: continue
        settled = r[0]; et = settled["event_ticker"]
        if et in seen: continue
        seen.add(et); tot += 1
        text = " ".join(str(settled.get(k, "")) for k in ("title", "rules_primary", "yes_sub_title", "no_sub_title"))
        ev = sb.match_game(espn, league, et, text)
        tl = None
        if ev:
            sm = espn.summary(league, ev["id"])
            tl = sb.timeline(sm, sport) if sm else None
        if not tl: miss += 1; continue
        out[et] = dict(start=tl["start"], end=tl["end"], sport=sport)
print(tot, "events", miss, "missing", len(out))
Path("/srv/kalshi/strategies/longshot-fade/research/schedule.json").write_text(json.dumps(out))
