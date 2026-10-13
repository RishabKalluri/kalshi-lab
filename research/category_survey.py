"""Where is the retail flow? Rank Kalshi series by how much takers lose (and so what liquidity providers earn).

Screening only (research/): decisions still come from the pipeline.

For a random sample of settled markets per series (pre-lockbox only), every trade is scored against how the market
settled, from the taker's side:
    taker edge = outcome of the side the taker bought (1/0) - price paid           (¢ per contract)
Negative taker edge = takers overpay = the passive side (makers) earned it, before maker fees. Split by the price the
taker paid shows the favourite-longshot bias. Taker fees use the series' fee schedule (quadratic: 0.07 * mult *
p(1-p) per contract, ignoring per-order rounding). CIs are bootstrapped over events (markets in one event are
correlated).

  python research/category_survey.py download --series KXHIGHNY KXNFLGAME ...   # into backfill/kalshi/<SERIES>/
  python research/category_survey.py analyze  [--series ...]                   # table from what's downloaded

Downloads use the same file format as `kalshi-lab backfill`, so the files are reusable by the engine.
"""

import argparse
import json
import logging
import os
import random
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from kalshi_lab.data.backfill import EXT, _write_atomic, settled_markets
from kalshi_lab.data.normalize import iso_ns
from kalshi_lab.rest import KalshiREST

log = logging.getLogger("survey")
ROOT = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill" / "kalshi"
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
SERIES = [
    # crypto / finance
    "KXBTC15M", "KXETH15M", "KXSOL15M", "KXXRP15M", "KXDOGE15M", "KXBTCD", "KXETHD", "KXINXU", "KXNASDAQ100U",
    "KXWTI", "KXEURUSD",
    # weather
    "KXHIGHNY", "KXHIGHLAX", "KXHIGHMIA", "KXHIGHCHI", "KXHIGHAUS", "KXRAIN", "KXLOWTNYC",
    # sports
    "KXNFLGAME", "KXNFLSPREAD", "KXNFLTOTAL", "KXNFLFIRSTTD", "KXNFLTD", "KXNFLRECYDS", "KXMLBGAME", "KXMLBTOTAL",
    "KXMLBHR", "KXNBAGAME", "KXNBATOTAL", "KXNHLGAME", "KXNCAAFGAME", "KXEPLGAME", "KXATPCHALLENGERMATCH",
    "KXWTAMATCH", "KXUFCFIGHT",
    # other
    "KXTRUMPMENTION", "KXRT", "KXAAAGASD", "KXCPI", "KXFEDDECISION",
]
CATEGORY = {**{s: "crypto/finance" for s in SERIES[:11]}, **{s: "weather" for s in SERIES[11:18]},
            **{s: "sports" for s in SERIES[18:35]}, **{s: "other" for s in SERIES[35:]}}
BUCKETS = [(0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.01)]


def lockbox_start() -> datetime:
    from kalshi_lab.validate import LOCKBOX_START
    d = LOCKBOX_START if isinstance(LOCKBOX_START, datetime) else datetime.fromisoformat(str(LOCKBOX_START))
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def download(series: list[str], max_markets: int, max_trades: int, seed: int):
    rest = KalshiREST(anonymous=True)
    end = lockbox_start()
    cutoff = datetime.fromisoformat(rest.get("/historical/cutoff")["trades_created_ts"].replace("Z", "+00:00"))
    for s in series:
        try:
            meta = rest.get(f"/series/{s}")["series"]
        except Exception as e:
            log.warning("%s: no series metadata (%r), skipping", s, e)
            continue
        # Stream the listing: ladder series have ~1M settled strikes, too many to hold in memory. Keep counts and a
        # reservoir sample of markets that traded (most strikes far from the money never trade).
        rng, keep = random.Random(seed), 20 * max_markets
        n_all = n_traded = 0
        vol, first, last, traded = 0.0, None, None, []
        try:
            for m, h in settled_markets(rest, s, START, end, cutoff):
                if m.get("result") not in ("yes", "no"):
                    continue
                n_all += 1
                v = float(m.get("volume_fp") or 0)
                vol += v
                first = min(first or m["close_time"], m["close_time"])
                last = max(last or m["close_time"], m["close_time"])
                if v <= 0:
                    continue
                n_traded += 1
                if len(traded) < keep:
                    traded.append((m, h))
                elif (j := rng.randrange(n_traded)) < keep:
                    traded[j] = (m, h)
        except Exception:
            log.exception("%s: listing failed, skipping (re-run to retry)", s)
            continue
        info = dict(series=s, category=meta.get("category"), fee_type=meta.get("fee_type"),
                    fee_multiplier=meta.get("fee_multiplier"), markets_total=n_all, volume_total=vol,
                    first_close=first, last_close=last)
        (ROOT / s).mkdir(parents=True, exist_ok=True)
        (ROOT / s / "_survey.json").write_text(json.dumps(info))
        rng.shuffle(traded)
        n_trades = n_mk = 0
        for m, historical in traded:
            if n_mk >= max_markets or n_trades >= max_trades:
                break
            path = ROOT / s / m["close_time"][:10] / f"{m['ticker']}{EXT}"
            if path.exists():
                n_mk += 1
                continue
            try:
                trades = list(rest.paginate("/historical/trades" if historical else "/markets/trades", "trades",
                                            ticker=m["ticker"], limit=1000))
            except Exception:
                log.exception("%s: failed, skipping", m["ticker"])
                continue
            trades.sort(key=lambda tr: tr["created_time"])
            lines = [(iso_ns(m["open_time"]), json.dumps({"event": "discovered",
                                                          "market": {**m, "result": "", "expiration_value": ""}}))]
            for tr in trades:
                msg = {"type": "trade", "msg": {"market_ticker": tr["ticker"], "yes_price_dollars": tr["yes_price_dollars"],
                                                "count_fp": tr["count_fp"], "taker_side": tr["taker_side"]}}
                lines.append((iso_ns(tr["created_time"]), json.dumps(msg)))
            lines.append((iso_ns(m["close_time"]) + 1, json.dumps({"event": "settled", "market": m})))
            _write_atomic(path, lines)
            n_mk += 1
            n_trades += len(trades)
        log.info("%s: %d settled (%d traded) in window, sampled %d markets / %d trades", s, n_all, n_traded,
                 n_mk, n_trades)


def _load(path: Path):
    """-> (event, settled market meta, [(taker paid, taker won, contracts)])"""
    import zstandard
    rows, settled = [], None
    for line in zstandard.ZstdDecompressor().decompress(path.read_bytes(), max_output_size=2**31).splitlines():
        m = json.loads(line)["m"]
        if m.get("type") == "trade":
            t = m["msg"]
            p, c = float(t["yes_price_dollars"]), float(t["count_fp"])
            rows.append((t["taker_side"], p, c))
        elif m.get("event") == "settled":
            settled = m["market"]
    if not settled or settled.get("result") not in ("yes", "no"):
        return None
    y = settled["result"] == "yes"
    out = [(p, y, c) if side == "yes" else (1 - p, not y, c) for side, p, c in rows]
    return settled["event_ticker"], settled, out


def _boot(per_event: dict, n=2000, seed=0):
    """Contract-weighted mean edge (¢) and 95% CI, resampling events."""
    ev = list(per_event.values())  # (sum edge*contracts, sum contracts)
    if not ev:
        return float("nan"), (float("nan"), float("nan"))
    a = np.array(ev)
    mean = 100 * a[:, 0].sum() / a[:, 1].sum()
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, len(a), size=(n, len(a)))
    s = a[idx]
    bs = 100 * s[:, :, 0].sum(1) / np.maximum(s[:, :, 1].sum(1), 1e-9)
    return mean, (float(np.percentile(bs, 2.5)), float(np.percentile(bs, 97.5)))


def analyze(series: list[str], out: Path | None, max_files: int = 1500):
    rows = []
    for s in series:
        d = ROOT / s
        files = sorted(d.glob(f"*/*{EXT}"))
        files = [f for f in files if START.strftime("%Y-%m-%d") <= f.parent.name < lockbox_start().strftime("%Y-%m-%d")]
        if len(files) > max_files:  # fully backfilled series (crypto 15M): same-size random sample
            files = sorted(random.Random(0).sample(files, max_files))
        if not files:
            continue
        info = json.loads((d / "_survey.json").read_text()) if (d / "_survey.json").exists() else {}
        mult = float(info.get("fee_multiplier") or 1)
        gross, net = defaultdict(lambda: [0.0, 0.0]), defaultdict(lambda: [0.0, 0.0])
        bucket = [defaultdict(lambda: [0.0, 0.0]) for _ in BUCKETS]
        n_tr = vol = 0
        for f in files:
            r = _load(f)
            if not r:
                continue
            event, _, trades = r
            for p, won, c in trades:
                e = (1.0 if won else 0.0) - p
                fee = 0.07 * mult * p * (1 - p)
                gross[event][0] += e * c
                gross[event][1] += c
                net[event][0] += (e - fee) * c
                net[event][1] += c
                for b, (lo, hi) in zip(bucket, BUCKETS):
                    if lo <= p < hi:
                        b[event][0] += e * c
                        b[event][1] += c
                n_tr += 1
                vol += c
        g, gci = _boot(gross)
        n, nci = _boot(net)
        span_days = 1.0
        if info.get("first_close") and info.get("last_close"):
            span_days = max(1.0, (iso_ns(info["last_close"]) - iso_ns(info["first_close"])) / 86400e9)
        rows.append(dict(series=s, category=CATEGORY.get(s, info.get("category")), fee_type=info.get("fee_type"),
                         fee_mult=mult, markets_sampled=len(files), events=len(gross), trades=n_tr, contracts=vol,
                         volume_per_day=info.get("volume_total", 0) / span_days,
                         markets_per_day=info.get("markets_total", 0) / span_days,
                         taker_gross_c=g, taker_gross_ci=gci, taker_net_c=n, taker_net_ci=nci,
                         buckets=[dict(lo=lo, hi=min(hi, 1.0), contracts=sum(v[1] for v in b.values()),
                                       taker_c=_boot(b)[0], ci=_boot(b)[1]) for b, (lo, hi) in zip(bucket, BUCKETS)]))
    rows.sort(key=lambda r: r["taker_gross_c"])
    print(f"{'series':22}{'cat':15}{'mkts':>5}{'ev':>5}{'contracts':>12}{'vol/day':>11}  "
          f"{'taker gross ¢ [CI]':>24}  {'taker net ¢':>11}   longshot<20 / fav>=80 (taker ¢)")
    for r in rows:
        b = r["buckets"]
        print(f"{r['series']:22}{r['category'] or '':15}{r['markets_sampled']:>5}{r['events']:>5}{r['contracts']:>12,.0f}"
              f"{r['volume_per_day']:>11,.0f}  {r['taker_gross_c']:>7.2f} [{r['taker_gross_ci'][0]:>6.2f},{r['taker_gross_ci'][1]:>6.2f}]"
              f"  {r['taker_net_c']:>11.2f}   {b[0]['taker_c']:>6.1f} / {b[4]['taker_c']:>6.1f}")
    if out:
        out.write_text(json.dumps(rows, indent=1, default=float))


def main(argv=None):
    p = argparse.ArgumentParser()
    p.add_argument("cmd", choices=["download", "analyze"])
    p.add_argument("--series", nargs="+", default=SERIES)
    p.add_argument("--max-markets", type=int, default=150)
    p.add_argument("--max-trades", type=int, default=1_500_000)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--out", type=Path)
    p.add_argument("--max-files", type=int, default=1500, help="analyze: sample at most this many markets per series")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)
    if a.cmd == "download":
        download(a.series, a.max_markets, a.max_trades, a.seed)
    else:
        analyze(a.series, a.out, a.max_files)


if __name__ == "__main__":
    sys.exit(main())
