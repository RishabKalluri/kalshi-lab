"""Turn raw (stream, recv_ns, message) triples from the recorder into normalized events.

Used both for replaying recorded logs and for paper trading off the live feed.
"""

import json
from datetime import datetime

from ..core.types import (BookDelta, BookSnapshot, FeedGap, MarketInfo, Side, SpotTick, Trade,
                          to_mills)


def iso_ns(s: str) -> int:
    return int(datetime.fromisoformat(s.replace("Z", "+00:00")).timestamp() * 1e9)


def _num(x) -> float | None:
    if x in (None, ""):
        return None
    try:
        return float(str(x).replace(",", ""))
    except ValueError:
        return None


def market_info(m: dict, ts: int) -> MarketInfo:
    return MarketInfo(
        ts=ts,
        ticker=m["ticker"],
        series=m["event_ticker"].split("-")[0],
        open_ts=iso_ns(m["open_time"]),
        close_ts=iso_ns(m["close_time"]),
        strike=m.get("floor_strike"),
        result=m.get("result") or None,
        settle_value=_num(m.get("expiration_value")),
        raw=m,
    )


def _ladder(levels) -> dict[int, float]:
    return {to_mills(p): float(q) for p, q in levels or []}


def kalshi_ws(ts: int, m: dict, stream: str):
    t = m.get("type")
    msg = m.get("msg", {})
    if t == "orderbook_delta":
        yield BookDelta(ts, msg["market_ticker"], msg["side"], to_mills(msg["price_dollars"]), float(msg["delta_fp"]))
    elif t == "trade":
        yield Trade(ts, msg["market_ticker"], to_mills(msg["yes_price_dollars"]), float(msg["count_fp"]),
                    Side.BUY if msg["taker_side"] == "yes" else Side.SELL)
    elif t == "orderbook_snapshot":
        yield BookSnapshot(ts, msg["market_ticker"], _ladder(msg.get("yes_dollars_fp")), _ladder(msg.get("no_dollars_fp")))
    elif t in ("_disconnect", "_connect"):
        yield FeedGap(ts, stream)


def kalshi_meta(ts: int, m: dict, stream: str):
    yield market_info(m["market"], ts)


def _f(x):
    return float(x) if x not in (None, "") else None


def spot(ts: int, m: dict, stream: str):
    src = stream.split("/", 1)[1]
    if src.startswith(("binance", "okx")) and m.get("type") == "ticker":  # backfilled closes
        yield SpotTick(ts, src, float(m["price"]))
    elif src.startswith("okx") and m.get("arg", {}).get("channel") == "tickers":
        for d in m.get("data", []):
            bid, ask = _f(d.get("bidPx")), _f(d.get("askPx"))
            yield SpotTick(ts, src, (bid + ask) / 2 if bid and ask else float(d["last"]), bid, ask)
    elif src.startswith("coinbase"):
        if m.get("type") == "ticker":
            yield SpotTick(ts, src, float(m["price"]), _f(m.get("best_bid")), _f(m.get("best_ask")))
    elif src.startswith("kraken"):
        ch = m.get("channel")
        if ch == "trade":
            for d in m.get("data", []):
                yield SpotTick(ts, src, float(d["price"]))
        elif ch == "ticker":
            for d in m.get("data", []):
                bid, ask = _f(d.get("bid")), _f(d.get("ask"))
                if bid and ask:
                    yield SpotTick(ts, src, (bid + ask) / 2, bid, ask)
    elif src.startswith("bitstamp"):
        if m.get("event") == "trade":
            yield SpotTick(ts, src, float(m["data"]["price"]))
    if m.get("type") in ("_disconnect",):
        yield FeedGap(ts, stream)


PARSERS = {"kalshi_ws": kalshi_ws, "kalshi_meta": kalshi_meta, "spot": spot}


def parse(stream: str, ts: int, raw: str | dict):
    m = json.loads(raw) if isinstance(raw, str) else raw
    return PARSERS[stream.split("/", 1)[0]](ts, m, stream)
