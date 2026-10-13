"""Do takers lose more (makers earn more) during stoppages than during live play in Kalshi sports game markets?

Screening only (research/): decisions still come from the pipeline.

Hypothesis: in a break (halftime, quarter break, timeout, two-minute warning, the gap after a score) no new game
information arrives, so informed in-game traders can't pick off resting quotes, while retail keeps trading.

Each settled market's trades (backfill files, pre-lockbox only) are matched to an ESPN game via the event ticker's date
and team codes plus the team names in the title/rules, then every trade is put in a phase using ESPN's play-by-play
wall-clock times:
    pre    before the first play (opening kickoff / tip / face-off); intensity over the last 2 h only
    live   from the first play to the end of the game, outside stoppages
    break  halftime + period + timeout below (the clean, no-information stoppages); score and long_gap are
           stoppages reported separately, not in "break" (a score's aftermath still carries reviews/PAT news)
    stoppage windows are [marker + BUF, next play) where the marker row is
             halftime  end of half (football, basketball), HT whistle (soccer), intermission (hockey)
             period    end of quarter 1/3, end of regulation before OT
             timeout   team / official (TV) timeout, two-minute warning (football, basketball)
             score     football scoring play: from score + SCORE_BUF to the next play (PAT, then kickoff usually
                       follows an official timeout row, which is classified as timeout)
             long_gap  any other gap between consecutive plays longer than LONG_GAP s (injury, review, missing rows)
           The first BUF seconds after a marker count as live: ESPN's wall clock is the play's start and is only
           accurate to a few seconds.
    post   END_BUF s after the end-of-game row onward
Live trades are also split by time since the last play's wall clock (football/basketball), which shows where the
reaction to each play lands and is a check on the clock alignment between ESPN and Kalshi.

Taker edge (same as category_survey.py): outcome of the side the taker bought (1/0) - price paid, ¢ per contract,
gross of fees. Negative = makers earned it. Also a 120 s markout: (last trade price 120 s later - price paid) from
the taker's side, a lower-variance (but bid/ask-bounce-biased) measure of adverse selection. CIs bootstrap over games
(all markets and series on one game are correlated). "game-eq" = mean over games of each game's contract-weighted
edge, so one huge game can't dominate.

  python research/sports_breaks.py [--series KXNFLGAME KXNFLSPREAD ...] [--root /srv/kalshi-data/backfill/kalshi]
                                   [--cache ~/kalshi-data/espn] [--out breaks.json]

ESPN responses (scoreboard per date, summary per game) are cached as JSON under --cache; uncached requests are spaced
by --delay seconds.
"""

import argparse
import hashlib
import json
import logging
import os
import re
import sys
import time
import urllib.request
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np

log = logging.getLogger("breaks")
ROOT = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill" / "kalshi"
CACHE = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "espn"
ESPN = "https://site.api.espn.com/apis/site/v2/sports/"
LEAGUE = {  # series -> (ESPN league path, sport)
    "KXNFLGAME": ("football/nfl", "football"), "KXNFLSPREAD": ("football/nfl", "football"),
    "KXNFLTOTAL": ("football/nfl", "football"), "KXNCAAFGAME": ("football/college-football", "football"),
    "KXNBAGAME": ("basketball/nba", "basketball"), "KXNHLGAME": ("hockey/nhl", "hockey"),
    "KXEPLGAME": ("soccer/eng.1", "soccer"),
}
SERIES = ["KXNFLGAME", "KXNFLSPREAD", "KXNFLTOTAL", "KXEPLGAME"]
NS = 1_000_000_000
BUF, SCORE_BUF, END_BUF, LONG_GAP = 15, 45, 30, 150   # seconds
SOCCER_HT_EST = (47 * 60, 15 * 60)                    # fallback: HT starts kickoff + 47 min, lasts 15 min
PRE_WINDOW = 2 * 3600                                 # pre-game intensity measured over the last 2 h before start
MARKOUT = 120
BUCKETS = [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]
CLEAN = ("halftime", "period", "timeout")              # "break" headline = these; score/long_gap reported apart
SINCE_PLAY = [(0, 15), (15, 40), (40, 10**9)]
MONTHS = {m: i + 1 for i, m in enumerate("JAN FEB MAR APR MAY JUN JUL AUG SEP OCT NOV DEC".split())}


def lockbox_start() -> datetime:
    try:
        from kalshi_lab.validate import LOCKBOX_START
    except ImportError:
        log.warning("kalshi_lab not importable: using lockbox start 2026-08-20 (check validate.py)")
        LOCKBOX_START = "2026-08-20"
    d = LOCKBOX_START if isinstance(LOCKBOX_START, datetime) else datetime.fromisoformat(str(LOCKBOX_START))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def _ts(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * NS)


# ---------------------------------------------------------------- ESPN

class Espn:
    def __init__(self, cache: Path, delay: float):
        self.cache, self.delay, self.last = cache, delay, 0.0
        cache.mkdir(parents=True, exist_ok=True)

    def get(self, url: str):
        f = self.cache / (hashlib.sha1(url.encode()).hexdigest()[:20] + ".json")
        if f.exists():
            return json.loads(f.read_text())
        time.sleep(max(0.0, self.delay - (time.time() - self.last)))
        for attempt in range(3):
            try:
                req = urllib.request.Request(url, headers={"User-Agent": "kalshi-lab research (cached, low rate)"})
                with urllib.request.urlopen(req, timeout=30) as r:
                    d = json.loads(r.read())
                break
            except Exception as e:
                log.warning("ESPN %s failed (%r), retry %d", url, e, attempt)
                time.sleep(5 * (attempt + 1))
        else:
            return None
        self.last = time.time()
        f.write_text(json.dumps(d))
        return d

    def scoreboard(self, league: str, day: datetime):
        extra = "&groups=80&limit=500" if "college" in league else "&limit=500"
        d = self.get(f"{ESPN}{league}/scoreboard?dates={day:%Y%m%d}{extra}")
        return (d or {}).get("events", [])

    def summary(self, league: str, gid: str):
        return self.get(f"{ESPN}{league}/summary?event={gid}")


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9 ]", "", s.lower().replace("&", "and"))


def match_game(espn: Espn, league: str, event_ticker: str, text: str):
    """event ticker like KXNFLGAME-26JAN11BUFJAC + title/rules text -> ESPN event dict or None."""
    m = re.match(r"[A-Z0-9]+-(\d{2})([A-Z]{3})(\d{2})(?:\d{4})?([A-Z]+)", event_ticker)
    if not m:
        return None
    day = datetime(2000 + int(m[1]), MONTHS[m[2]], int(m[3]), tzinfo=timezone.utc)
    codes, text = m[4], " " + _norm(text) + " "
    for d in (day, day - timedelta(days=1), day + timedelta(days=1)):
        hits = []
        for ev in espn.scoreboard(league, d):
            comps = ev["competitions"][0]["competitors"]
            ok = 0
            for c in comps:
                t = c["team"]
                ab = t.get("abbreviation", "")
                names = {t.get(k, "") for k in ("location", "displayName", "shortDisplayName", "name", "nickname")}
                by_code = bool(ab) and (codes.startswith(ab) or codes.endswith(ab))
                by_name = any(len(n) > 2 and f" {_norm(n)} " in text for n in names if n)
                ok += by_code or by_name
            if ok == len(comps) == 2:
                hits.append(ev)
        if len(hits) == 1:
            return hits[0]
        if len(hits) > 1:  # e.g. both LA teams on one date: require codes for both
            strict = [ev for ev in hits if all(
                (lambda ab: codes.startswith(ab) or codes.endswith(ab))(c["team"].get("abbreviation", "@"))
                for c in ev["competitions"][0]["competitors"])]
            return strict[0] if len(strict) == 1 else None
    return None


def _marker(p: dict, sport: str):
    t = (p.get("type") or {}).get("text", "").lower()
    per = (p.get("period") or {}).get("number")
    if "end of game" in t or t == "end game":
        return "end"
    if "end of half" in t:
        return "halftime"
    if t in ("end period", "period end", "end quarter", "end of quarter"):
        if sport == "hockey":
            return "halftime" if per in (1, 2) else "period"
        return "halftime" if per == 2 else "period"
    if "timeout" in t or "two-minute" in t or "two minute" in t:
        return "timeout"
    if sport == "football" and p.get("scoringPlay"):
        return "score"
    return None


def timeline(summary: dict, sport: str):
    """-> dict(start, end, segs=[(t0, t1, phase, sub)], plays=[snap times], approx=bool) in ns, or None."""
    if sport == "soccer":
        ke = [k for k in summary.get("keyEvents", []) if k.get("wallclock")]
        typ = lambda k: (k.get("type") or {}).get("text", "").lower()
        ko = [k for k in ke if typ(k) == "kickoff"]
        ht = [k for k in ke if typ(k) == "halftime"]
        h2 = [k for k in ke if "2nd half" in typ(k) or "second half" in typ(k)]
        end = [k for k in ke if typ(k).startswith("end regular") or typ(k) in ("full time", "end of match")]
        if not ko or not end:
            return None
        start, stop = _ts(ko[0]["wallclock"]), _ts(end[-1]["wallclock"])
        approx = not (ht and h2)
        h0 = _ts(ht[0]["wallclock"]) if ht else start + SOCCER_HT_EST[0] * NS
        h1 = _ts(h2[0]["wallclock"]) if h2 else h0 + SOCCER_HT_EST[1] * NS
        segs = [(start, h0 + BUF * NS, "live", "live"), (h0 + BUF * NS, h1, "break", "halftime"),
                (h1, stop + END_BUF * NS, "live", "live")]
        return dict(start=start, end=stop, segs=segs, plays=[], approx=approx)
    plays = summary.get("plays") or [p for dr in (summary.get("drives") or {}).get("previous", [])
                                     for p in dr.get("plays", [])]
    if not plays:
        return None
    have = [p for p in plays if p.get("wallclock")]
    if len(have) < 0.9 * len(plays) or len(have) < 30:
        return None
    rows = sorted(((_ts(p["wallclock"]), _marker(p, sport)) for p in have), key=lambda r: r[0])
    start = rows[0][0]
    ends = [w for w, mk in rows if mk == "end"]
    stop = ends[-1] if ends else rows[-1][0]
    rows = [r for r in rows if r[0] <= stop]
    segs, snaps = [], []
    for (w, mk), (w2, _) in zip(rows, rows[1:] + [(stop + END_BUF * NS, None)]):
        if mk is None:
            snaps.append(w)
        if w2 <= w:
            continue
        sub = mk if mk in ("halftime", "period", "timeout", "score") else None
        if sub is None and w2 - w > LONG_GAP * NS:
            sub, b = "long_gap", 30
        else:
            b = SCORE_BUF if sub == "score" else BUF
        if sub and w2 - w > b * NS:
            segs += [(w, w + b * NS, "live", "live"), (w + b * NS, w2, "break", sub)]
        else:
            segs.append((w, w2, "live", "live"))
    return dict(start=start, end=stop, segs=segs, plays=snaps, approx=False)


# ---------------------------------------------------------------- Kalshi files

def load(path: Path):
    """-> (settled market meta, discovered meta, times ns, taker paid, taker won, contracts, taker side is yes)"""
    import zstandard
    t, side, p, c, settled, disc = [], [], [], [], None, None
    for line in zstandard.ZstdDecompressor().decompress(path.read_bytes(), max_output_size=2**31).splitlines():
        r = json.loads(line)
        m = r["m"]
        if m.get("type") == "trade":
            x = m["msg"]
            t.append(r["t"])
            side.append(x["taker_side"] == "yes")
            p.append(float(x["yes_price_dollars"]))
            c.append(float(x["count_fp"]))
        elif m.get("event") == "settled":
            settled = m["market"]
        elif m.get("event") == "discovered":
            disc = m["market"]
    if not settled or settled.get("result") not in ("yes", "no") or not t:
        return None
    t, side, p, c = np.array(t, dtype=np.int64), np.array(side), np.array(p), np.array(c)
    o = np.argsort(t, kind="stable")
    t, side, p, c = t[o], side[o], p[o], c[o]
    y = settled["result"] == "yes"
    paid = np.where(side, p, 1 - p)
    won = np.where(side, y, not y).astype(float)
    # markout: last trade price MARKOUT s later (yes terms), from the taker's side
    j = np.searchsorted(t, t + MARKOUT * NS, side="right") - 1
    later = p[j]
    mk = np.where(side, later - p, p - later)
    mk_ok = t[-1] >= t + MARKOUT * NS  # a later trade exists at/after the horizon
    return settled, disc or settled, t, paid, won, c, mk, mk_ok


# ---------------------------------------------------------------- stats

def boot(per_game: dict, n=2000, seed=0):
    """per_game: game -> (sum x*c, sum c). -> (cw mean ¢, cw CI, game-eq mean ¢, game-eq CI, games)"""
    a = np.array([v for v in per_game.values() if v[1] > 0], dtype=float)
    if len(a) == 0:
        return dict(cw=np.nan, cw_ci=(np.nan, np.nan), ge=np.nan, ge_ci=(np.nan, np.nan), games=0)
    g = a[:, 0] / a[:, 1]
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(n, len(a)))
    s = a[idx]
    cw = 100 * s[:, :, 0].sum(1) / s[:, :, 1].sum(1)
    ge = 100 * g[idx].mean(1)
    pc = lambda x: (float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5)))
    return dict(cw=100 * a[:, 0].sum() / a[:, 1].sum(), cw_ci=pc(cw), ge=100 * g.mean(), ge_ci=pc(ge), games=len(a))


def boot_diff(A: dict, B: dict, n=2000, seed=1):
    """A - B (¢) over games that have both, cw and game-eq, paired bootstrap over games."""
    ks = [k for k in A if k in B and A[k][1] > 0 and B[k][1] > 0]
    if len(ks) < 3:
        return None
    a, b = np.array([A[k] for k in ks]), np.array([B[k] for k in ks])
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(ks), size=(n, len(ks)))
    cw = lambda x, i: x[i][..., 0].sum(-1) / x[i][..., 1].sum(-1)
    d_cw = 100 * (cw(a, idx) - cw(b, idx))
    gd = a[:, 0] / a[:, 1] - b[:, 0] / b[:, 1]
    d_ge = 100 * gd[idx].mean(1)
    pc = lambda x: (float(np.percentile(x, 2.5)), float(np.percentile(x, 97.5)))
    full = np.arange(len(ks))
    return dict(games=len(ks), cw=float(100 * (cw(a, full) - cw(b, full))), cw_ci=pc(d_cw),
                ge=float(100 * gd.mean()), ge_ci=pc(d_ge))


# ---------------------------------------------------------------- main analysis

def _since_key(lo, hi):
    return f"live:{lo}-{hi if hi < 10**9 else ''}s"


def analyze(series: list[str], root: Path, espn: Espn, out: Path | None, max_files: int):
    lb = lockbox_start().strftime("%Y-%m-%d")
    # groups: (series or pooled label, key) -> game -> [edge*c, c, n, markout*c, c_markout]
    acc = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0, 0, 0.0, 0.0]))
    bucket = defaultdict(lambda: defaultdict(lambda: [0.0, 0.0]))
    dur = defaultdict(float)  # (label, key) -> seconds of exposure (once per game per label)
    react = defaultdict(lambda: np.zeros(13))  # label -> contracts per 5 s bin since last snap (0..60 s, >60)
    react_exp = defaultdict(lambda: np.zeros(13))
    cover, dur_done = {}, set()
    timelines, matched = {}, {}
    for s in series:
        league, sport = LEAGUE[s]
        files = sorted(f for f in (root / s).glob("*/*.jsonl.zst") if f.parent.name < lb)[:max_files]
        n_files = n_match = n_tl = n_approx = 0
        seen_games = set()
        labels = [s, "ALL"] + (["NFL (3 series)"] if s.startswith("KXNFL") else [])
        for f in files:
            r = load(f)
            if not r:
                continue
            n_files += 1
            settled, disc, t, paid, won, c, mko, mk_ok = r
            ev_t = settled["event_ticker"]
            if ev_t not in matched:
                text = " ".join(str(settled.get(k, "")) for k in ("title", "rules_primary", "yes_sub_title",
                                                                    "no_sub_title"))
                matched[ev_t] = match_game(espn, league, ev_t, text)
            ev = matched[ev_t]
            if not ev:
                log.debug("%s: no ESPN match (%s)", f.name, settled.get("title"))
                continue
            n_match += 1
            gid = ev["id"]
            if gid not in timelines:
                sm = espn.summary(league, gid)
                timelines[gid] = timeline(sm, sport) if sm else None
            tl = timelines[gid]
            if not tl:
                continue
            n_tl += 1
            n_approx += tl["approx"]
            seen_games.add((s, gid))
            for lab in labels:
                if (lab, gid) in dur_done:
                    continue
                dur_done.add((lab, gid))
                dur[(lab, "pre:last2h")] += PRE_WINDOW
                for a0, a1, ph, sub in tl["segs"]:
                    if ph == "live" or sub in CLEAN:
                        dur[(lab, ph)] += (a1 - a0) / NS
                    if ph == "break":
                        dur[(lab, "break:" + sub)] += (a1 - a0) / NS
                if tl["plays"]:
                    for L in np.diff(np.array(tl["plays"] + [tl["end"]], dtype=np.int64)) / NS:
                        react_exp[lab][:12] += np.clip(L - np.arange(0, 60, 5), 0, 5)
                        react_exp[lab][12] += max(0.0, L - 60)
                        for lo, hi in SINCE_PLAY:
                            dur[(lab, _since_key(lo, hi))] += float(np.clip(L - lo, 0, hi - lo))
            # classify trades (vectorised)
            seg = tl["segs"]
            s0 = np.array([x[0] for x in seg], dtype=np.int64)
            s1 = np.array([x[1] for x in seg], dtype=np.int64)
            sk = np.array([x[2] if x[2] == "live" else "break:" + x[3] for x in seg] + ["live"], dtype=object)
            k = np.searchsorted(s0, t, side="right") - 1
            inside = (k >= 0) & (t < s1[np.maximum(k, 0)])
            key = sk[np.where(inside, k, len(seg))]
            key[t < tl["start"]] = "pre"
            key[t >= tl["end"] + END_BUF * NS] = "post"
            is_live, is_break = key == "live", np.isin(key, ["break:" + x for x in CLEAN])
            masks = {"pre": key == "pre", "pre:last2h": (key == "pre") & (t >= tl["start"] - PRE_WINDOW * NS),
                     "live": is_live, "break": is_break, "post": key == "post"}
            for sub in ("halftime", "period", "timeout", "score", "long_gap"):
                masks["break:" + sub] = key == "break:" + sub
            if tl["plays"]:
                snaps = np.array(tl["plays"], dtype=np.int64)
                j = np.searchsorted(snaps, t, side="right") - 1
                since = np.where(j >= 0, (t - snaps[np.maximum(j, 0)]) / NS, -1.0)
                ok = is_live & (j >= 0)
                for lo, hi in SINCE_PLAY:
                    masks[_since_key(lo, hi)] = ok & (since >= lo) & (since < hi)
                rb = np.minimum((since[ok] // 5).astype(int), 12)
                rc = np.bincount(rb, weights=c[ok], minlength=13)
            e = won - paid
            bidx = np.searchsorted([b[1] for b in BUCKETS], paid, side="right")
            for lab in labels:
                for kname, m in masks.items():
                    if not m.any():
                        continue
                    a = acc[(lab, kname)][gid]
                    a[0] += float((e[m] * c[m]).sum())
                    a[1] += float(c[m].sum())
                    a[2] += int(m.sum())
                    mm = m & mk_ok
                    a[3] += float((mko[mm] * c[mm]).sum())
                    a[4] += float(c[mm].sum())
                for ph, m in (("live", is_live), ("break", is_break)):
                    for bi in range(len(BUCKETS)):
                        mb = m & (bidx == bi)
                        if mb.any():
                            b = bucket[(lab, ph, bi)][gid]
                            b[0] += float((e[mb] * c[mb]).sum())
                            b[1] += float(c[mb].sum())
                if tl["plays"]:
                    react[lab] += rc
        cover[s] = dict(files=n_files, matched=n_match, with_timeline=n_tl, soccer_ht_estimated=n_approx,
                        events=len({k for k, v in matched.items() if k.startswith(s + "-")}),
                        events_matched=len({k for k, v in matched.items() if k.startswith(s + "-") and v}),
                        games=len({g for (lab, g) in seen_games if lab == s}))
        log.info("%s: %s", s, cover[s])

    # ---- report
    labels = [s for s in series if s in cover] + ([lab for lab in ("NFL (3 series)",) if any(
        s.startswith("KXNFL") for s in cover)]) + (["ALL"] if len(cover) > 1 else [])
    keys = ["pre", "pre:last2h", "live", "break", "post", "break:halftime", "break:period", "break:timeout", "break:score",
            "break:long_gap"] + [_since_key(lo, hi) for lo, hi in SINCE_PLAY]
    res = dict(coverage=cover, params=dict(BUF=BUF, SCORE_BUF=SCORE_BUF, END_BUF=END_BUF, LONG_GAP=LONG_GAP,
                                           MARKOUT=MARKOUT), rows=[], diffs=[], buckets=[], react={})
    print("\nCoverage (market files -> matched to ESPN game -> with usable play-by-play timing):")
    for s, cv in cover.items():
        print(f"  {s:13} files {cv['files']:>5}  matched {cv['matched']:>5}  timed {cv['with_timeline']:>5}   "
              f"events {cv['events_matched']}/{cv['events']} matched, games {cv['games']}"
              + (f", soccer HT estimated in {cv['soccer_ht_estimated']} files" if cv["soccer_ht_estimated"] else ""))
    hdr = (f"{'group':15}{'phase':16}{'games':>6}{'trades':>9}{'contracts':>12}{'ct/min':>9}"
           f"  {'taker ¢ (contract-wt) [95% CI]':>31}  {'taker ¢ (game-eq) [95% CI]':>28}  {'mko120 ¢':>8}")
    for lab in labels:
        print("\n" + hdr)
        for key in keys:
            g = acc.get((lab, key))
            if not g:
                continue
            st = boot({k: (v[0], v[1]) for k, v in g.items()})
            mk = sum(v[3] for v in g.values()) / max(sum(v[4] for v in g.values()), 1e-9) * 100
            n_tr, ct = sum(v[2] for v in g.values()), sum(v[1] for v in g.values())
            d = dur.get((lab, key))
            cpm = ct / (d / 60) if d else float("nan")
            row = dict(group=lab, phase=key, trades=n_tr, contracts=ct, minutes=(d or 0) / 60, cpm=cpm,
                       markout_c=mk, **st)
            res["rows"].append(row)
            print(f"{lab:15}{key:16}{st['games']:>6}{n_tr:>9,}{ct:>12,.0f}{cpm:>9,.0f}"
                  f"  {st['cw']:>7.2f} [{st['cw_ci'][0]:>6.2f},{st['cw_ci'][1]:>6.2f}]      "
                  f"  {st['ge']:>7.2f} [{st['ge_ci'][0]:>6.2f},{st['ge_ci'][1]:>6.2f}]    {mk:>8.2f}")
    print("\nBreak minus live (taker ¢; negative = takers do worse in breaks = better for makers), paired by game:")
    for lab in labels:
        for key in ["break", "break:halftime", "break:timeout", "break:period", "break:score"]:
            A, B = acc.get((lab, key)), acc.get((lab, "live"))
            if not A or not B:
                continue
            d = boot_diff({k: (v[0], v[1]) for k, v in A.items()}, {k: (v[0], v[1]) for k, v in B.items()})
            if d:
                res["diffs"].append(dict(group=lab, phase=key, **d))
                print(f"  {lab:15}{key:16} games {d['games']:>4}   contract-wt {d['cw']:>6.2f} "
                      f"[{d['cw_ci'][0]:>6.2f},{d['cw_ci'][1]:>6.2f}]   game-eq {d['ge']:>6.2f} "
                      f"[{d['ge_ci'][0]:>6.2f},{d['ge_ci'][1]:>6.2f}]")
    print("\nBy taker price (contract-wt taker ¢ [CI], contracts):")
    for lab in labels:
        for ph in ("live", "break"):
            cells = []
            for bi, (lo, hi) in enumerate(BUCKETS):
                g = bucket.get((lab, ph, bi), {})
                st = boot(g)
                ct = sum(v[1] for v in g.values())
                res["buckets"].append(dict(group=lab, phase=ph, lo=lo, hi=min(hi, 1.0), contracts=ct, **st))
                cells.append(f"{lo:.1f}-{min(hi, 1):.1f}: {st['cw']:>6.1f} [{st['cw_ci'][0]:>5.1f},{st['cw_ci'][1]:>5.1f}]"
                             f" {ct / 1e3:>6.0f}k")
            print(f"  {lab:15}{ph:6}" + " | ".join(cells))
    print("\nLive intensity by seconds since the last play's ESPN wall clock (contracts/min; alignment check:")
    print("the reaction to a play should peak a few seconds after the snap):")
    for lab in labels:
        if react_exp[lab].sum() > 0:
            v = react[lab] / np.maximum(react_exp[lab] / 60, 1e-9)
            res["react"][lab] = v.tolist()
            print(f"  {lab:15}" + " ".join(f"{int(x):>6}" for x in v) + "   (bins 0-5,5-10,...,55-60,>60 s)")
    if out:
        out.write_text(json.dumps(res, indent=1, default=float))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("--series", nargs="+", default=SERIES, choices=list(LEAGUE))
    p.add_argument("--root", type=Path, default=ROOT)
    p.add_argument("--cache", type=Path, default=CACHE)
    p.add_argument("--delay", type=float, default=0.7, help="seconds between uncached ESPN requests")
    p.add_argument("--max-files", type=int, default=100_000)
    p.add_argument("--out", type=Path)
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    analyze(a.series, a.root, Espn(a.cache, a.delay), a.out, a.max_files)


if __name__ == "__main__":
    sys.exit(main())
