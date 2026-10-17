"""Per check (60 s), score state from ESPN plays (wallclock) joined with market last price. -> /tmp/lf_scores.pkl
row: series, event, ticker, ck_sec_in, lead(for this team), tleft_s, p_last, won"""
import sys, json, re, numpy as np, zstandard, pickle
from pathlib import Path
sys.path.insert(0, "/srv/kalshi/research")
import sports_breaks as sb
sched = json.loads(Path("/srv/kalshi/strategies/longshot-fade/research/schedule.json").read_text())
root = Path("/srv/kalshi-data/backfill/kalshi"); lb = sb.lockbox_start().strftime("%Y-%m-%d")
espn = sb.Espn(Path("/srv/kalshi/research/data/espn"), 0.1); NS = 10**9; LAG = 5
def tleft(sport, per, clk):
    try: m, s = clk.split(":"); sec = int(m) * 60 + float(s)
    except Exception: return None
    if sport == "basketball": return (4 - per) * 720 + sec if per <= 4 else sec
    return (3 - per) * 1200 + sec if per <= 3 else sec
out = []; bad = 0
for s in ("KXNBAGAME", "KXNHLGAME"):
    league, sport = sb.LEAGUE[s]; evs = {}
    for f in sorted(root.glob(f"{s}/*/*.jsonl.zst")):
        if f.parent.name >= lb: continue
        t, p, res, meta = [], [], None, None
        for line in zstandard.ZstdDecompressor().decompress(f.read_bytes(), max_output_size=2**31).splitlines():
            r = json.loads(line); m = r["m"]
            if m.get("type") == "trade": t.append(r["t"]); p.append(float(m["msg"]["yes_price_dollars"]))
            elif m.get("event") == "settled": res = m["market"]["result"]; meta = m["market"]
        if res not in ("yes", "no") or not t or meta["event_ticker"] not in sched: continue
        et = meta["event_ticker"]
        if et not in evs:
            text = " ".join(str(meta.get(k, "")) for k in ("title", "rules_primary", "yes_sub_title", "no_sub_title"))
            ev = sb.match_game(espn, league, et, text)
            sm = espn.summary(league, ev["id"]) if ev else None
            if not sm: evs[et] = None; continue
            plays = [(sb._ts(pl["wallclock"]), pl["homeScore"], pl["awayScore"], pl["period"]["number"], pl["clock"]["displayValue"])
                     for pl in sm.get("plays", []) if pl.get("wallclock") and "homeScore" in pl and pl.get("period")]
            plays.sort(key=lambda x: x[0])
            comps = {c["homeAway"]: c["team"] for c in ev["competitions"][0]["competitors"]}
            evs[et] = (plays, comps)
        if evs[et] is None: continue
        plays, comps = evs[et]
        sub = _n = sb._norm(meta.get("yes_sub_title", ""))
        def is_team(tm): return any(len(n) > 2 and (sb._norm(n) in sub or sub in sb._norm(n)) for n in (tm.get(k, "") for k in ("location","displayName","shortDisplayName","name")) if n)
        side = "home" if is_team(comps["home"]) and not is_team(comps["away"]) else "away" if is_team(comps["away"]) and not is_team(comps["home"]) else None
        if side is None: bad += 1; continue
        t = np.array(t); p = np.array(p); o = np.argsort(t, kind="stable"); t, p = t[o], p[o]
        pw = np.array([x[0] for x in plays]); g = sched[et]
        for ck in range(g["start"] + 60 * NS, g["end"], 60 * NS):
            j = np.searchsorted(t, ck, side="right") - 1
            if j < 0 or ck - t[j] > 300 * NS: continue
            k = np.searchsorted(pw, ck - LAG * NS, side="right") - 1
            if k < 0: continue
            _, hs, as_, per, clk = plays[k]; tl = tleft(sport, per, clk)
            if tl is None: continue
            lead = (hs - as_) * (1 if side == "home" else -1)
            out.append((s, et, f.stem, (ck - g["start"]) / NS, lead, tl, p[j], res == "yes", per, ck))
print(len(out), "rows", bad, "bad side")
pickle.dump(out, open("/tmp/lf_scores.pkl", "wb"))
