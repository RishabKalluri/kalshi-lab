"""Real-order smoke test of the live exchange code, before live trading: two post-only orders far from the market
(a 1c bid and a 99c offer on the newest KXETH15M market, which cannot fill), each cancelled after a second.
Checks: Kalshi accepts our order format, we get the exchange id, the private websocket reports the cancel, and
nothing is left resting. Run on the server:  uv run python scripts/live_order_test.py
"""
import time

from kalshi_lab.core.types import TIF, Order, Side
from kalshi_lab.live.exchange import KalshiExchange
from kalshi_lab.rest import KalshiREST

rest = KalshiREST()
print("balance before:", rest.get("/portfolio/balance")["balance_dollars"])
mkts = rest.get("/markets", series_ticker="KXETH15M", status="open")["markets"]
m = sorted(mkts, key=lambda x: x["close_time"])[-1]  # newest market: most time left
print("market", m["ticker"], "yes_bid", m.get("yes_bid_dollars"), "yes_ask", m.get("yes_ask_dollars"))
ex = KalshiExchange(dry_run=False)
time.sleep(2)  # let the private websocket connect
tests = [Order(1, m["ticker"], Side.BUY, 10, 1, TIF.POST, 0, "test"),    # bid YES at 1c
         Order(2, m["ticker"], Side.SELL, 990, 1, TIF.POST, 0, "test")]  # offer YES at 99c (= bid NO at 1c)
for o in tests:
    ex.submit(o, 0)
    for _ in range(50):
        ex.process_until(0, {})
        if o.xid or o.status == "rejected":
            break
        time.sleep(0.1)
    print(f"order {o.id} {o.side.name} @ {o.price / 10:.0f}c: status={o.status} exchange_id={o.xid or 'NONE'}")
    time.sleep(1)
    ex.process_until(0, {})
    ex.cancel(o, 0)
    for _ in range(50):
        ex.process_until(0, {})
        if o.status == "cancelled":
            break
        time.sleep(0.1)
    print(f"   after cancel: status={o.status} (via the private websocket)")
time.sleep(1)
left = rest.get("/portfolio/orders", ticker=m["ticker"], status="resting").get("orders", [])
print("resting orders left on Kalshi:", len(left))
print("balance after:", rest.get("/portfolio/balance")["balance_dollars"])
