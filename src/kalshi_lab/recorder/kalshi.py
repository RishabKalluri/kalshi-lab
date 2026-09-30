"""Records Kalshi orderbook deltas, trades and tickers for every open market in a series.

Streams written:
  kalshi_ws/<SERIES>    raw websocket messages (snapshots, deltas, trades, tickers, markers)
  kalshi_meta/<SERIES>  REST market rows: on discovery, and once more after settlement (has `result`)
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from urllib.parse import urlparse

import websockets

from ..auth import WS_URL, KalshiAuth
from ..rest import KalshiREST
from .sink import Sink

log = logging.getLogger(__name__)

CHANNELS = ["orderbook_delta", "trade", "ticker"]


class SeqGap(Exception):
    pass


class KalshiRecorder:
    def __init__(self, series: str, sink: Sink, poll_s: float = 10.0):
        self.series = series
        self.sink = sink
        self.poll_s = poll_s
        self.auth = KalshiAuth()
        self.rest = KalshiREST(self.auth)
        self.ws_stream = f"kalshi_ws/{series}"
        self.meta_stream = f"kalshi_meta/{series}"
        self.known: set[str] = set()  # markets whose metadata we've written
        self.unsettled: set[str] = set()  # left the open list, waiting for a result
        self.settled: set[str] = set()
        self.no_strike: set[str] = set()  # discovered before floor_strike was published
        self.open_time: dict[str, float] = {}

    def _marker(self, kind: str, **kw):
        self.sink.write(self.ws_stream, json.dumps({"type": f"_{kind}", **kw}))

    async def _recover_recent(self, hours: float = 3):
        """After a restart: pick up markets that closed recently so their settlements still get recorded."""
        since = int(time.time() - hours * 3600)
        recent = await asyncio.to_thread(
            lambda: list(self.rest.markets(series_ticker=self.series, min_close_ts=since, max_close_ts=int(time.time()))))
        for m in recent:
            self.known.add(m["ticker"])
            if m.get("result"):
                self.sink.write(self.meta_stream, json.dumps({"event": "settled", "market": m}))
                self.settled.add(m["ticker"])
            else:
                self.unsettled.add(m["ticker"])
        log.info("%s: recovered %d recently closed markets", self.series, len(recent))

    async def run(self):
        try:
            await self._recover_recent()
        except Exception:
            log.exception("%s: couldn't recover recent markets", self.series)
        backoff = 1
        while True:
            try:
                await self._session()
                backoff = 1
            except (SeqGap, websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as e:
                log.warning("%s: session ended (%r), reconnecting in %ss", self.series, e, backoff)
            self._marker("disconnect")
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 30)

    async def _session(self):
        headers = self.auth.headers("GET", urlparse(WS_URL).path)
        async with websockets.connect(WS_URL, additional_headers=headers, max_queue=None) as ws:
            self._marker("connect")
            subscribed: set[str] = set()
            seqs: dict[int, int] = {}
            next_id = 1

            async def discover_once():
                nonlocal next_id
                # Everything closing in the next 30 min: the live market plus the next one(s), so we're
                # subscribed before they open and capture the book from the first tick.
                now = int(time.time())
                open_markets = await asyncio.to_thread(
                    lambda: list(self.rest.markets(series_ticker=self.series, min_close_ts=now,
                                                   max_close_ts=now + 1800))
                )
                open_tickers = {m["ticker"] for m in open_markets}
                for m in open_markets:
                    t = m["ticker"]
                    if t not in self.known:
                        self.known.add(t)
                        self.open_time[t] = datetime.fromisoformat(m["open_time"].replace("Z", "+00:00")).timestamp()
                        self.sink.write(self.meta_stream, json.dumps({"event": "discovered", "market": m}))
                        if m.get("floor_strike") is None:
                            self.no_strike.add(t)
                    elif t in self.no_strike and m.get("floor_strike") is not None:
                        self.no_strike.discard(t)
                        self.sink.write(self.meta_stream, json.dumps({"event": "updated", "market": m}))
                new = sorted(open_tickers - subscribed)
                if new:
                    await ws.send(json.dumps({
                        "id": next_id, "cmd": "subscribe",
                        "params": {"channels": CHANNELS, "market_tickers": new},
                    }))
                    next_id += 1
                    subscribed.update(new)
                    log.info("%s: subscribed %s", self.series, new)
                self.unsettled |= self.known - open_tickers - self.settled
                await self._check_settlements()

            async def discover():
                while True:
                    try:
                        await discover_once()
                    except websockets.ConnectionClosed:
                        raise
                    except Exception:
                        log.exception("%s: market discovery failed, retrying", self.series)
                    # Poll fast while an opened market is still missing its strike.
                    await asyncio.sleep(2 if self._awaiting_strike() else self.poll_s)

            task = asyncio.create_task(discover())
            try:
                while True:
                    if task.done():  # discovery died: tear down and reconnect rather than silently stop
                        raise ConnectionError(f"discovery task ended: {task.exception()!r}")
                    raw = await asyncio.wait_for(ws.recv(), timeout=60)
                    self.sink.write(self.ws_stream, raw)
                    msg = json.loads(raw)
                    sid, seq = msg.get("sid"), msg.get("seq")
                    # Every message carrying a seq counts, including `ok` acks for subscription updates.
                    if seq is not None and sid is not None:
                        last = seqs.get(sid)
                        if last is not None and seq != last + 1:
                            raise SeqGap(f"sid={sid} expected {last + 1} got {seq}")
                        seqs[sid] = seq
                    if msg.get("type") == "error":
                        log.error("%s: ws error %s", self.series, raw)
            finally:
                task.cancel()

    def _awaiting_strike(self) -> bool:
        return any(time.time() >= self.open_time.get(t, float("inf")) for t in self.no_strike)

    async def _check_settlements(self):
        for ticker in list(self.unsettled):
            m = (await asyncio.to_thread(self.rest.get, f"/markets/{ticker}"))["market"]
            if m.get("result"):
                self.sink.write(self.meta_stream, json.dumps({"event": "settled", "market": m}))
                self.unsettled.discard(ticker)
                self.settled.add(ticker)
                log.info("%s: %s settled %s", self.series, ticker, m["result"])
