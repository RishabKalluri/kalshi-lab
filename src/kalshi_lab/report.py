"""Summaries of a finished Engine run."""

import csv
from collections import Counter
import json
import math
from datetime import datetime, timezone
from pathlib import Path


def summarize(engine) -> dict:
    pf = engine.portfolio
    per = [(t, pf.by_market[t]) for _, t, _ in engine.settlements]
    pnls = [m["pnl"] for _, m in per]
    traded = [p for (_, m), p in zip(per, pnls) if m["fills"] > 0]
    n = len(traded)
    mean = sum(traded) / n if n else 0.0
    sd = math.sqrt(sum((x - mean) ** 2 for x in traded) / (n - 1)) if n > 1 else 0.0
    eq, peak, mdd = 0.0, 0.0, 0.0
    for p in pnls:
        eq += p
        peak = max(peak, eq)
        mdd = max(mdd, peak - eq)
    vol = sum(f.qty for f in engine.fills)
    maker = sum(f.qty for f in engine.fills if f.maker)
    return {
        "markets_seen": len(engine.ctx.markets),
        "markets_settled": len(engine.settlements),
        "markets_traded": n,
        "pnl": round(sum(pnls), 2),  # settled markets only
        "equity_change": round(engine.equity() - pf.start_cash, 2),  # incl. open positions at mid
        "bankroll": pf.start_cash,
        "return_pct": round(100 * sum(pnls) / pf.start_cash, 2) if pf.start_cash else None,
        "fees": round(pf.fees, 2),
        "pnl_before_fees": round(sum(pnls) + pf.fees, 2),
        "open_positions": {t: round(q, 2) for t, q in pf.pos.items() if abs(q) > 1e-9},
        "fills": len(engine.fills),
        "contracts": round(vol, 2),
        "maker_share": round(maker / vol, 3) if vol else None,
        "pnl_per_contract": round(sum(pnls) / vol, 4) if vol else None,
        "win_rate": round(sum(p > 0 for p in traded) / n, 3) if n else None,
        "mean_pnl_per_traded_market": round(mean, 3),
        "t_stat": round(mean / (sd / math.sqrt(n)), 2) if n > 1 and sd > 0 else None,
        "max_drawdown": round(mdd, 2),
        "orders": len(engine.ctx.orders),
        "orders_filled": sum(1 for o in engine.ctx.orders.values() if o.filled > 0),
        "orders_missed": sum(1 for o in engine.ctx.orders.values() if o.filled <= 0 and o.status in ("cancelled", "rejected")),
        "rejects": len(engine.ctx.rejects),
        "reject_reasons": dict(Counter(r.split(" ")[0] if r.startswith("qty") else r
                                       for _, _, r in engine.ctx.rejects).most_common(3)),
        "events": engine.events,
    }


def print_summary(s: dict):
    w = max(map(len, s))
    for k, v in s.items():
        print(f"  {k:<{w}}  {v}")


def save(engine, summary: dict, out: Path, meta: dict):
    out.mkdir(parents=True, exist_ok=True)
    (out / "summary.json").write_text(json.dumps({**meta, **summary}, indent=2, default=str))
    with open(out / "fills.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time", "ticker", "side", "price", "qty", "fee", "maker", "tag", "order_id"])
        for f in engine.fills:
            w.writerow([_iso(f.ts), f.ticker, f.side.value, f.price, f.qty, f.fee, f.maker, f.tag, f.order_id])
    save_timeline(engine, out)
    with open(out / "orders.csv", "w", newline="") as fh:  # every order, incl. IOCs that missed
        w = csv.writer(fh)
        w.writerow(["submitted", "ticker", "side", "price", "qty", "tif", "filled", "status", "tag"])
        for o in engine.ctx.orders.values():
            w.writerow([_iso(o.submit_ts), o.ticker, o.side.value, o.price, o.qty, o.tif.value, round(o.filled, 2),
                        o.status, o.tag])
    with open(out / "markets.csv", "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["settle_time", "ticker", "open_time", "close_time", "strike", "settle_value", "result", "pnl",
                    "fees", "fills", "volume", "maker_qty", "taker_qty", "final_pos"])
        for ts, t, pnl in engine.settlements:
            m = engine.portfolio.by_market[t]
            info = engine.ctx.markets.get(t)
            w.writerow([_iso(ts), t, _iso(info.open_ts) if info else "", _iso(info.close_ts) if info else "",
                        info.strike if info else "", info.settle_value if info else "", m["result"], round(pnl, 4),
                        round(m["fees"], 2), m["fills"], round(m["volume"], 2), round(m["maker_qty"], 2),
                        round(m["taker_qty"], 2), round(m["final_pos"], 2)])


def save_timeline(engine, out: Path):
    if not engine.timeline:
        return
    import gzip
    cols = ["ts", "ticker", "bid", "ask", "spot", "strike", "pos"]
    extra = sorted({k for r in engine.timeline for k in r} - set(cols))
    with gzip.open(out / "timeline.csv.gz", "wt", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(["time"] + cols[1:] + extra)
        for r in engine.timeline:
            w.writerow([_iso(r["ts"])] + [_fmt(r.get(c)) for c in cols[1:] + extra])


def _fmt(v):
    if v is None:
        return ""
    return round(v, 4) if isinstance(v, float) else v


def _iso(ns: int) -> str:
    return datetime.fromtimestamp(ns / 1e9, timezone.utc).isoformat(timespec="milliseconds")
