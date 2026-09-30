"""Real order routing to Kalshi, behind the same interface as SimExchange.

Orders go to the V2 endpoint (POST /portfolio/events/orders, side bid = buy YES, ask = sell YES,
YES price in dollars). Fills arrive on the authenticated `fill` websocket channel and order state
on `user_orders`; both are turned into engine Fills / Order status on the engine thread.

`dry_run=True` logs the requests it would send and never touches the order endpoints.
"""

import asyncio
import json
import logging
import queue
import threading
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlparse

import httpx
import websockets

from ..auth import WS_URL, KalshiAuth
from ..core.types import TIF, Fill, Order, Side, to_mills
from ..rest import KalshiREST

log = logging.getLogger("live.exchange")

TIF_API = {TIF.GTC: "good_till_canceled", TIF.IOC: "immediate_or_cancel", TIF.POST: "good_till_canceled"}


class KalshiExchange:
    def __init__(self, dry_run: bool = True, run_id: str | None = None):
        self.dry_run = dry_run
        self.run_id = run_id or uuid.uuid4().hex[:8]
        self.rest = KalshiREST()
        self.auth = self.rest.auth
        self.pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="orders")
        self.inbox: queue.Queue = queue.Queue()  # ('fill'|'order'|'ack'|'reject', payload) from other threads
        self.by_client: dict[str, Order] = {}
        self.by_exchange: dict[str, Order] = {}
        self.seen_trades: set[str] = set()
        self.close_ts: dict[str, int] = {}
        if not dry_run:
            threading.Thread(target=self._ws_thread, daemon=True, name="private-ws").start()

    # --- strategy-facing ---------------------------------------------------
    def submit(self, o: Order, now: int):
        cid = f"{self.run_id}-{o.id}"
        self.by_client[cid] = o
        body = {
            "ticker": o.ticker,
            "client_order_id": cid,
            "side": "bid" if o.side == Side.BUY else "ask",
            "count": f"{o.qty:.2f}",
            "price": f"{o.price / 1000:.4f}",
            "time_in_force": TIF_API[o.tif],
            "self_trade_prevention_type": "taker_at_cross",
            "exchange_index": -1,
        }
        if o.tif == TIF.POST:
            body["post_only"] = True
        if self.dry_run:
            log.info("DRY RUN would POST /portfolio/events/orders %s", body)
            o.status = "rejected"
            return
        self.pool.submit(self._post, o, cid, body)

    def cancel(self, o: Order, now: int):
        if self.dry_run:
            log.info("DRY RUN would cancel %s", o)
            return
        self.pool.submit(self._cancel, o)

    def _post(self, o: Order, cid: str, body: dict):
        try:
            r = self.rest.post("/portfolio/events/orders", body)
            self.inbox.put(("ack", (o, r)))
        except httpx.HTTPStatusError as e:
            self.inbox.put(("reject", (o, f"{e.response.status_code} {e.response.text[:300]}")))
        except Exception as e:  # network: order state unknown, reconcile via user_orders
            log.exception("order post failed for %s", cid)
            self.inbox.put(("reject", (o, repr(e))))

    def _cancel(self, o: Order):
        oid = o.xid
        for _ in range(50):  # wait briefly for the ack if the cancel raced the submit
            if oid:
                break
            time.sleep(0.02)
            oid = o.xid
        if not oid:
            log.warning("cancel: no exchange id for %s", o)
            return
        try:
            self.rest.delete(f"/portfolio/events/orders/{oid}", market_ticker=o.ticker, exchange_index=-1)
        except httpx.HTTPStatusError as e:
            log.warning("cancel %s failed: %s %s", oid, e.response.status_code, e.response.text[:200])

    def cancel_everything(self):
        """Emergency / shutdown: cancel every resting order this run placed."""
        for o in list(self.by_client.values()):
            if o.is_live and o.xid:
                self._cancel(o)

    # --- engine-facing -------------------------------------------------------
    def process_until(self, t: int, books) -> list[Fill]:
        fills = []
        while True:
            try:
                kind, payload = self.inbox.get_nowait()
            except queue.Empty:
                return fills
            if kind == "ack":
                o, r = payload
                o.xid = r["order_id"]
                self.by_exchange[r["order_id"]] = o
                if o.status == "pending":
                    left = float(r["remaining_count"])
                    o.status = "filled" if left <= 0 else ("open" if o.tif in (TIF.GTC, TIF.POST) else "cancelled")
            elif kind == "reject":
                o, why = payload
                o.status = "rejected"
                log.warning("order %s rejected: %s", o.id, why)
            elif kind == "order":
                m = payload
                o = self.by_client.get(m.get("client_order_id")) or self.by_exchange.get(m["order_id"])
                if o is None:
                    continue
                o.xid = m["order_id"]
                self.by_exchange[m["order_id"]] = o
                o.status = {"resting": "open", "canceled": "cancelled", "executed": "filled"}.get(m["status"], o.status)
            elif kind == "fill":
                m = payload
                if m["trade_id"] in self.seen_trades:
                    continue
                self.seen_trades.add(m["trade_id"])
                o = self.by_client.get(m.get("client_order_id")) or self.by_exchange.get(m["order_id"])
                if o is None:
                    log.warning("fill for unknown order %s (placed outside this run?)", m["order_id"])
                    continue
                q = float(m["count_fp"])
                o.filled += q
                fills.append(Fill(m["ts_ms"] * 1_000_000, o.id, o.ticker, o.side, to_mills(m["yes_price_dollars"]), q,
                                  float(m["fee_cost"]), not m["is_taker"], o.tag))

    # Book/trade hooks exist for interface parity with SimExchange.
    def on_delta(self, d, book): ...
    def on_snapshot(self, ticker): ...
    def on_trade(self, tr) -> list[Fill]:
        return []
    def on_close(self, ticker): ...

    # --- private websocket -----------------------------------------------------
    def _ws_thread(self):
        asyncio.run(self._ws_loop())

    async def _ws_loop(self):
        backoff = 1
        while True:
            try:
                headers = self.auth.headers("GET", urlparse(WS_URL).path)
                async with websockets.connect(WS_URL, additional_headers=headers) as ws:
                    await ws.send(json.dumps({"id": 1, "cmd": "subscribe", "params": {"channels": ["fill", "user_orders"]}}))
                    backoff = 1
                    async for raw in ws:
                        m = json.loads(raw)
                        if m.get("type") == "fill":
                            self.inbox.put(("fill", m["msg"]))
                        elif m.get("type") == "user_order":
                            self.inbox.put(("order", m["msg"]))
                        elif m.get("type") == "error":
                            log.error("private ws error: %s", raw)
            except Exception as e:
                log.warning("private ws: %r, reconnecting in %ss", e, backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 30)
