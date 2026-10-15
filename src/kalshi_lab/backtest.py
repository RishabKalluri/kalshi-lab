"""kalshi-lab backtest <strategy> [options]

<strategy> is 'path/to/file.py:ClassName' or 'package.module:ClassName'.

  kalshi-lab backtest strategies/fair_value.py:FairValue --series KXBTC15M \
      --source recorded --start 2026-09-29T00:00 --end 2026-09-29T06:00 -p edge=40

  --sweep edge=20,40,60   runs one backtest per value in parallel and prints a comparison.
"""

import argparse
import importlib
import importlib.util
import itertools
import json
import logging
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

from .core.fees import Fees
from .core.risk import RiskLimits
from .data.source import BackfillSource, BooksSource, RecordedSource
from .engine import Engine
from .recorder.config import book_depth, spot_map
from .report import print_summary, save, summarize
from .sim.exchange import SimExchange
from .sizing import DEFAULT_MAX_FRAC, DEFAULT_SIZING
from .sizing import parse as parse_sizing


def load_strategy(spec: str):
    from .strategy_dir import strategy_spec
    spec = strategy_spec(spec)  # a strategy folder/slug -> its strategy.py (+ class from config.json)
    target, _, cls = spec.partition(":")
    if target.endswith(".py"):
        path = Path(target).resolve()
        name = f"strategy_{path.parent.name}_{path.stem}".replace("-", "_")  # unique per folder
        mod_spec = importlib.util.spec_from_file_location(name, path)
        mod = importlib.util.module_from_spec(mod_spec)
        sys.modules[name] = mod
        mod_spec.loader.exec_module(mod)
    else:
        mod = importlib.import_module(target)
    if not cls:
        from .strategy import Strategy
        cands = [v for v in vars(mod).values()
                 if isinstance(v, type) and issubclass(v, Strategy) and v is not Strategy and v.__module__ == mod.__name__]
        if len(cands) != 1:
            raise SystemExit(f"{spec}: specify the class, found {[c.__name__ for c in cands]}")
        return cands[0]
    return getattr(mod, cls)


def _val(v: str):
    try:
        return json.loads(v)
    except json.JSONDecodeError:
        return v


def parse_params(items) -> dict:
    return {k: _val(v) for k, v in (i.split("=", 1) for i in items or [])}


def _dt(s: str) -> datetime:
    d = datetime.fromisoformat(s)
    return d if d.tzinfo else d.replace(tzinfo=timezone.utc)


def run_one(args: dict) -> dict:
    """One backtest. Takes/returns plain dicts so it can run in a worker process."""
    logging.basicConfig(level=args["log_level"], format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    cls = load_strategy(args["strategy"])
    strat = cls(**args["params"])
    start, end = _dt(args["start"]), _dt(args["end"])
    from .validate import lockbox_guard
    lockbox_guard(start, end)  # lockbox dates only via the pipeline's lockbox stage (or the user's own tools)
    recorded = args["source"] == "recorded"
    has_book = args["source"] in ("recorded", "books")  # books: historical order books (data/books.py)
    smap = spot_map(args["series"], backfill=not recorded)
    if args["spot"]:  # explicit override: these streams for every series
        smap = {s: list(args["spot"]) for s in args["series"]}
    src_cls = {"recorded": RecordedSource, "books": BooksSource}.get(args["source"], BackfillSource)
    source = src_cls(args["series"], start, end, spot=sorted({x for v in smap.values() for x in v}))
    risk = RiskLimits(**args["risk"])
    exch = SimExchange(latency_ms=args["latency_ms"], fees=Fees(), queue_frac=args.get("queue_frac", 1.0))
    t0 = time.time()
    # 1-minute candle feeds (coinbase backfill) need a longer freshness window than live/1s feeds.
    stale = 90 if any(("coinbase" in x or x.endswith("_1m")) for v in smap.values() for x in v) and not recorded else 5
    eng = Engine(strat, source, exch, risk=risk, timer_ms=args["timer_ms"], has_book=has_book,
                 spot_stale_s=stale, start_ts=int(start.timestamp() * 1e9),
                 timeline_s=args.get("timeline_s") or None, spot_map=smap,
                 sizer=parse_sizing(args.get("sizing"), args.get("max_frac", DEFAULT_MAX_FRAC)), cash=args.get("bankroll", 1000.0),
                 synthetic_depth={s: d for s in args["series"] if (d := book_depth(s))} if not has_book else None)
    eng.run()
    summary = summarize(eng)
    summary["wall_s"] = round(time.time() - t0, 1)
    if args.get("out"):
        meta = {k: args.get(k) for k in ("strategy", "params", "series", "source", "start", "end", "latency_ms",
                                          "queue_frac", "sizing", "bankroll", "risk")}
        meta["resolved_params"] = vars(strat.p)
        save(eng, summary, Path(args["out"]), meta)
    return summary


def main(argv=None):
    p = argparse.ArgumentParser(prog="kalshi-lab backtest", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("strategy")
    p.add_argument("--series", nargs="+", default=["KXBTC15M"])
    p.add_argument("--source", choices=["recorded", "backfill", "books"], default="recorded")
    p.add_argument("--start", help="UTC ISO time (default: --hours before --end)")
    p.add_argument("--end", help="UTC ISO time (default: now)")
    p.add_argument("--hours", type=float, default=24)
    p.add_argument("--spot", nargs="*", help="spot streams to load, e.g. coinbase_btcusd (default: all)")
    p.add_argument("-p", "--param", action="append", help="strategy param override, key=value")
    p.add_argument("--sweep", action="append", help="key=v1,v2,... (cartesian product across --sweep flags)")
    p.add_argument("--latency-ms", type=float, default=150)
    p.add_argument("--timer-ms", type=int, default=1000)
    p.add_argument("--queue-frac", type=float, default=1.0,
                   help="where resting orders join the queue: 1 = behind everything (default), 0.5 = halfway")
    p.add_argument("--max-position", type=float, default=500)
    p.add_argument("--max-order-qty", type=float, default=100)
    p.add_argument("--max-loss", type=float)
    p.add_argument("--out", help="results dir (default: results/<strategy>-<time>)")
    p.add_argument("--workers", type=int, default=os.cpu_count())
    p.add_argument("--sizing", default=DEFAULT_SIZING,
                   help=f"pct:P | fixed:N | risk:DOLLARS | kelly:FRACTION (default {DEFAULT_SIZING})")
    p.add_argument("--bankroll", type=float, default=1000.0, help="starting equity for sizing and returns")
    p.add_argument("--max-frac", type=float, default=DEFAULT_MAX_FRAC, help="max fraction of equity at risk per market")
    p.add_argument("--timeline-s", type=float, default=5, help="seconds between chart samples (0 = off)")
    p.add_argument("-v", "--verbose", action="store_true")
    a = p.parse_args(argv)

    end = _dt(a.end) if a.end else datetime.now(timezone.utc)
    start = _dt(a.start) if a.start else end - timedelta(hours=a.hours)
    name = a.strategy.split(":")[-1] or Path(a.strategy).stem
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    out = Path(a.out or f"results/{Path(a.strategy.split(':')[0]).stem}-{stamp}")
    base = dict(strategy=a.strategy, params=parse_params(a.param), series=a.series, source=a.source,
                start=start.isoformat(), end=end.isoformat(), spot=a.spot, latency_ms=a.latency_ms,
                timer_ms=a.timer_ms, timeline_s=a.timeline_s, queue_frac=a.queue_frac, sizing=a.sizing,
                bankroll=a.bankroll, max_frac=a.max_frac, log_level=logging.INFO if a.verbose else logging.WARNING,
                risk=dict(max_position=a.max_position, max_order_qty=a.max_order_qty, max_loss=a.max_loss))
    logging.basicConfig(level=base["log_level"], format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    print(f"{name}  {a.source}  {', '.join(a.series)}  {start:%Y-%m-%d %H:%M} -> {end:%Y-%m-%d %H:%M} UTC  "
          f"latency={a.latency_ms}ms")

    if not a.sweep:
        s = run_one({**base, "out": str(out)})
        print_summary(s)
        print(f"results: {out}/")
        return

    keys = [s.split("=", 1)[0] for s in a.sweep]
    values = [[_val(v) for v in s.split("=", 1)[1].split(",")] for s in a.sweep]
    grid = [dict(zip(keys, combo)) for combo in itertools.product(*values)]
    jobs = [{**base, "params": {**base["params"], **g}, "out": str(out / "_".join(f"{k}={v}" for k, v in g.items()))}
            for g in grid]
    with ProcessPoolExecutor(max_workers=min(a.workers, len(jobs))) as pool:
        results = list(pool.map(run_one, jobs))
    cols = ["pnl", "fees", "contracts", "markets_traded", "pnl_per_contract", "win_rate", "t_stat", "max_drawdown"]
    head = " ".join(f"{k:>10}" for k in keys) + " " + " ".join(f"{c:>16}" for c in cols)
    print(head)
    for g, r in zip(grid, results):
        print(" ".join(f"{str(g[k]):>10}" for k in keys) + " " + " ".join(f"{str(r[c]):>16}" for c in cols))
    print(f"results: {out}/")
