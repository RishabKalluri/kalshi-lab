from kalshi_lab.core.book import Book
from kalshi_lab.core.fees import Fees
from kalshi_lab.core.portfolio import Portfolio
from kalshi_lab.core.risk import RiskLimits
from kalshi_lab.core.types import TIF, BookDelta, BookSnapshot, Order, Side, Trade
from kalshi_lab.sim.exchange import SimExchange

MS = 1_000_000


def mkbook(yes=None, no=None, ticker="T"):
    b = Book(ticker)
    b.apply_snapshot(BookSnapshot(0, ticker, yes or {}, no or {}))
    return b


def order(side, price, qty, tif=TIF.GTC, oid=1, ts=0):
    return Order(oid, "T", side, price, qty, tif, ts)


def test_book_yes_terms():
    b = mkbook(yes={500: 10, 490: 5}, no={480: 7, 470: 3})
    assert b.best_bid == 500 and b.best_ask == 520
    assert b.asks() == [(520, 7), (530, 3)]
    assert b.ask_qty(530) == 3
    b.apply_delta(BookDelta(1, "T", "no", 480, -7))
    assert b.best_ask == 530


def test_fees_match_kalshi_formula():
    f = Fees()
    assert f(500, 100, maker=False) == 1.75       # 0.07*100*.5*.5
    assert f(500, 1, maker=False) == 0.02         # 0.0175 rounds up to a cent
    assert f(990, 10, maker=False) == 0.01
    assert f(500, 100, maker=True) == 0.0


def test_taker_walks_levels_after_latency_and_remembers_consumption():
    ex = SimExchange(latency_ms=100)
    books = {"T": mkbook(no={480: 5, 470: 10})}  # asks 520x5, 530x10
    o = order(Side.BUY, 530, 8, TIF.IOC)
    ex.submit(o, 0)
    assert ex.process_until(99 * MS, books) == []  # not arrived yet
    fills = ex.process_until(100 * MS, books)
    assert [(f.price, f.qty) for f in fills] == [(520, 5), (530, 3)]
    assert o.status == "filled"
    # Same displayed liquidity can't be taken twice.
    o2 = order(Side.BUY, 520, 5, TIF.IOC, oid=2, ts=200 * MS)
    ex.submit(o2, 200 * MS)
    assert ex.process_until(400 * MS, books) == [] and o2.status == "cancelled"


def test_taker_uses_book_at_arrival_not_submission():
    ex = SimExchange(latency_ms=100)
    books = {"T": mkbook(no={480: 5})}
    o = order(Side.BUY, 520, 5, TIF.IOC)
    ex.submit(o, 0)
    books["T"].apply_delta(BookDelta(50 * MS, "T", "no", 480, -5))  # ask pulled before we arrive
    assert ex.process_until(100 * MS, books) == []
    assert o.status == "cancelled"


def test_resting_order_waits_for_queue_then_fills():
    ex = SimExchange(latency_ms=0)
    books = {"T": mkbook(yes={500: 10}, no={480: 10})}
    o = order(Side.BUY, 500, 5)
    ex.submit(o, 0)
    ex.process_until(0, books)
    assert o.status == "open" and o.queue_ahead == 10
    assert ex.on_trade(Trade(1, "T", 500, 8, Side.SELL)) == []      # eats queue ahead
    fills = ex.on_trade(Trade(2, "T", 500, 4, Side.SELL))           # 2 left ahead, 2 for us
    assert [(f.price, f.qty, f.maker) for f in fills] == [(500, 2, True)]
    fills = ex.on_trade(Trade(3, "T", 490, 100, Side.SELL))         # trade through our price
    assert [(f.qty) for f in fills] == [3] and o.status == "filled"


def test_resting_order_ignores_wrong_side_trades_and_cancel():
    ex = SimExchange(latency_ms=10)
    books = {"T": mkbook(yes={500: 0.0}, no={480: 10})}
    o = order(Side.SELL, 600, 5)
    ex.submit(o, 0)
    ex.process_until(10 * MS, books)
    assert ex.on_trade(Trade(20 * MS, "T", 650, 5, Side.SELL)) == []  # seller-initiated, doesn't lift us
    ex.cancel(o, 30 * MS)
    fills = ex.on_trade(Trade(35 * MS, "T", 650, 5, Side.BUY))        # cancel not yet arrived -> fill
    assert [f.qty for f in fills] == [5]


def test_orders_rejected_after_close():
    ex = SimExchange(latency_ms=100)
    ex.close_ts["T"] = 50 * MS
    books = {"T": mkbook(no={480: 5})}
    o = order(Side.BUY, 520, 5, TIF.IOC)
    ex.submit(o, 0)
    ex.process_until(100 * MS, books)
    assert o.status == "rejected"


def test_portfolio_settlement_long_and_short():
    from kalshi_lab.core.types import Fill
    pf = Portfolio()
    pf.apply(Fill(0, 1, "A", Side.BUY, 400, 10, 0.17, False))
    assert round(pf.settle("A", "yes"), 2) == round(10 * 0.6 - 0.17, 2)
    pf.apply(Fill(0, 2, "B", Side.SELL, 400, 10, 0.0, True))       # short YES == long NO at 0.60
    assert round(pf.settle("B", "no"), 2) == 4.0
    assert round(pf.cash, 2) == round(6 - 0.17 + 4, 2)


def test_risk_counts_open_orders():
    r = RiskLimits(max_position=10)
    open_ = [order(Side.BUY, 500, 6, oid=9)]
    assert r.check(order(Side.BUY, 500, 5), 0, open_) is not None
    assert r.check(order(Side.SELL, 500, 5), 0, open_) is None


def test_snap_price_to_tapered_ticks():
    from kalshi_lab.core.types import snap_price
    assert snap_price(523, Side.BUY) == 520
    assert snap_price(523, Side.SELL) == 530
    assert snap_price(52, Side.BUY) == 52       # deci-cent region
    assert snap_price(955, Side.SELL) == 955
    assert snap_price(900, Side.BUY) == 900


def test_orders_rejected_before_open():
    ex = SimExchange(latency_ms=0)
    ex.open_ts["T"] = 100 * MS
    books = {"T": mkbook(no={480: 5})}
    o = order(Side.BUY, 520, 5, TIF.IOC)
    ex.submit(o, 0)
    ex.process_until(0, books)
    assert o.status == "rejected"


def test_queue_frac_puts_order_partway_into_queue():
    ex = SimExchange(latency_ms=0, queue_frac=0.5)
    books = {"T": mkbook(yes={500: 10}, no={480: 10})}
    o = order(Side.BUY, 500, 5)
    ex.submit(o, 0)
    ex.process_until(0, books)
    assert o.queue_ahead == 5
    assert [f.qty for f in ex.on_trade(Trade(1, "T", 500, 7, Side.SELL))] == [2]


def test_post_only_rejected_when_crossing_and_rests_otherwise():
    ex = SimExchange(latency_ms=0)
    books = {"T": mkbook(yes={500: 10}, no={480: 10})}  # 50 / 52
    cross = order(Side.BUY, 520, 5, TIF.POST)
    ex.submit(cross, 0)
    assert ex.process_until(0, books) == [] and cross.status == "rejected"
    rest = order(Side.BUY, 510, 5, TIF.POST, oid=2)
    ex.submit(rest, 0)
    ex.process_until(0, books)
    assert rest.status == "open" and rest.queue_ahead == 0
