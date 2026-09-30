"""Public spot-exchange feeds for the underlying. Each feed writes raw messages to spot/<name>."""

import asyncio
import json
import logging

import websockets

from .config import stream_name
from .sink import Sink

log = logging.getLogger(__name__)

# name -> (url, list of subscribe messages). Symbols are per-exchange.
FEEDS = {
    "coinbase": lambda sym: ("wss://ws-feed.exchange.coinbase.com", [
        {"type": "subscribe", "product_ids": [sym], "channels": ["ticker", "heartbeat"]},
    ]),
    "kraken": lambda sym: ("wss://ws.kraken.com/v2", [
        {"method": "subscribe", "params": {"channel": "trade", "symbol": [sym]}},
        {"method": "subscribe", "params": {"channel": "ticker", "symbol": [sym], "event_trigger": "bbo"}},
    ]),
    "bitstamp": lambda sym: ("wss://ws.bitstamp.net", [
        {"event": "bts:subscribe", "data": {"channel": f"live_trades_{sym}"}},
    ]),
    "okx": lambda sym: ("wss://ws.okx.com:8443/ws/v5/public", [
        {"op": "subscribe", "args": [{"channel": "tickers", "instId": sym}]},
    ]),
}


async def run_feed(spec: str, sink: Sink):
    """spec is '<exchange>:<symbol>', e.g. 'coinbase:BTC-USD'."""
    exchange, sym = spec.split(":", 1)
    url, subs = FEEDS[exchange](sym)
    stream = f"spot/{stream_name(spec)}"
    backoff = 1
    while True:
        try:
            async with websockets.connect(url, max_queue=None) as ws:
                for s in subs:
                    await ws.send(json.dumps(s))
                sink.write(stream, json.dumps({"type": "_connect"}))
                backoff = 1
                while True:
                    sink.write(stream, await asyncio.wait_for(ws.recv(), timeout=60))
        except (websockets.ConnectionClosed, OSError, asyncio.TimeoutError) as e:
            log.warning("%s: %r, reconnecting in %ss", spec, e, backoff)
        sink.write(stream, json.dumps({"type": "_disconnect"}))
        await asyncio.sleep(backoff)
        backoff = min(backoff * 2, 30)
