from kalshi_lab.core.types import TIF, BookDelta, BookSnapshot, MarketInfo, Side, SpotTick, Trade
from kalshi_lab.engine import Engine
from kalshi_lab.sim.exchange import SimExchange
from kalshi_lab.strategy import Strategy

S = 1_000_000_000


def market(result=None, ts=0):
    return MarketInfo(ts, "M", "X", open_ts=0, close_ts=900 * S, strike=100.0, result=result)


class BuyOnce(Strategy):
    params = {"side": "buy", "tif": "ioc", "price": 600}

    def on_start(self, ctx):
        self.done = False
        self.fills = []
        self.settled = []

    def on_timer(self, ctx):
        if not self.done and ctx.book("M"):
            fn = ctx.buy if self.p.side == "buy" else ctx.sell
            fn("M", self.p.price, 10, tif=TIF(self.p.tif))
            self.done = True

    def on_fill(self, ctx, f):
        self.fills.append(f)

    def on_settle(self, ctx, m, pnl):
        self.settled.append((m.ticker, m.result, pnl))


def events(result):
    return [
        market(ts=1),
        BookSnapshot(2, "M", yes_bids={580: 50}, no_bids={400: 50}),  # 58 / 60
        SpotTick(3, "coinbase", 101.0),
        BookDelta(3 * S, "M", "yes", 580, 1),
        market(result=result, ts=1000 * S),
    ]


def test_taker_buy_then_settle_yes():
    st = BuyOnce()
    eng = Engine(st, events("yes"), SimExchange(latency_ms=100)).run()
    assert [(f.price, f.qty, f.maker) for f in st.fills] == [(600, 10, False)]
    fee = st.fills[0].fee
    assert fee == 0.17  # ceil(0.07*10*.6*.4 = 0.168)
    assert abs(st.settled[0][2] - (10 * (1 - 0.6) - fee)) < 1e-9
    assert abs(eng.portfolio.cash - (4.0 - fee)) < 1e-9


def test_taker_sell_then_settle_yes_loses():
    st = BuyOnce(side="sell", price=580)
    eng = Engine(st, events("yes"), SimExchange(latency_ms=100)).run()
    assert [(f.side, f.price) for f in st.fills] == [(Side.SELL, 580)]
    assert abs(st.settled[0][2] - (-(10 * 0.42) - st.fills[0].fee)) < 1e-9


def test_resting_bid_fills_on_trade_through():
    st = BuyOnce(tif="gtc", price=590)  # inside the spread: rests with nobody ahead
    evs = events("no")
    evs.insert(4, Trade(5 * S, "M", 585, 4, Side.SELL))
    eng = Engine(st, evs, SimExchange(latency_ms=100)).run()
    assert [(f.price, f.qty, f.maker) for f in st.fills] == [(590, 4, True)]
    assert abs(st.settled[0][2] - (-4 * 0.59)) < 1e-9  # maker fee 0 on quadratic series


def test_warmup_hides_events_before_start():
    seen = []

    class Rec(Strategy):
        def on_spot(self, ctx, t):
            seen.append(t.ts)

    evs = [market(ts=1), SpotTick(2, "a", 1.0), SpotTick(5 * S, "a", 2.0)]
    eng = Engine(Rec(), evs, SimExchange(), start_ts=3 * S).run()
    assert seen == [5 * S]
    assert "M" in eng.ctx.markets


def test_spot_only_blends_the_series_own_feeds():
    from kalshi_lab.core.portfolio import Portfolio
    from kalshi_lab.core.risk import RiskLimits
    from kalshi_lab.strategy import Context
    ctx = Context(None, RiskLimits(), Portfolio(), spot_map={"BTC": ["cb_btc", "kr_btc"], "ETH": ["cb_eth"]})
    ctx.now = 10 * S
    ctx._spot = {"cb_btc": (10 * S, 100.0), "kr_btc": (9 * S, 102.0), "cb_eth": (10 * S, 5.0)}
    assert ctx.spot(series="BTC") == 101.0
    assert ctx.spot(series="ETH") == 5.0
    ctx._spot["kr_btc"] = (1 * S, 102.0)  # stale (>5s) -> excluded
    assert ctx.spot(series="BTC") == 100.0


def _ctx(equity=1000.0, books=None):
    from kalshi_lab.core.portfolio import Portfolio
    from kalshi_lab.core.risk import RiskLimits
    from kalshi_lab.strategy import Context
    ctx = Context(None, RiskLimits(), Portfolio(cash=equity))
    ctx.books = books or {}
    return ctx


def test_sizing_policies():
    from kalshi_lab.core.book import Book
    from kalshi_lab.sizing import Fixed, FixedRisk, Kelly
    ctx = _ctx()
    assert Fixed(contracts=7)(ctx, "M", Side.BUY, 600) == 7
    assert FixedRisk(dollars=30)(ctx, "M", Side.BUY, 600) == 50        # $30 / $0.60
    assert FixedRisk(dollars=30)(ctx, "M", Side.SELL, 600) == 75       # selling YES at .60 risks .40
    # Kelly: p=.7 at cost .6 -> f*=(.7-.6)/.4=.25; quarter Kelly on $1000 = $62.5 -> 104 contracts, capped at 10% = 166
    assert Kelly(fraction=0.25, max_frac=0.10)(ctx, "M", Side.BUY, 600, prob=0.7) == 104
    assert Kelly(fraction=0.25)(ctx, "M", Side.BUY, 600, prob=0.55) == 0   # negative edge
    assert Kelly(fraction=1.0, max_frac=0.10)(ctx, "M", Side.BUY, 600, prob=0.9) == 166  # exposure cap
    b = Book("M")
    b.apply_snapshot(BookSnapshot(0, "M", {590: 5}, {400: 12}))       # ask 600 x 12
    ctx.books = {"M": b}
    assert Fixed(contracts=50)(ctx, "M", Side.BUY, 600, tif=TIF.IOC) == 12  # can't take more than displayed


def test_default_sizing_is_one_percent_of_equity():
    from kalshi_lab.sizing import parse
    ctx = _ctx(equity=1000.0)
    assert parse()(ctx, "M", Side.BUY, 500) == 20      # $10 at risk / $0.50
    assert parse()(ctx, "M", Side.SELL, 800) == 50     # $10 / $0.20


def test_quick_gate():
    from kalshi_lab.validate import quick_gate
    bad = {"a": {"pnl": -10, "contracts": 100, "ci95_c": [-9, -1]}, "b": {"pnl": -2, "contracts": 50, "ci95_c": [-5, 3]}}
    unclear = {"a": {"pnl": -10, "contracts": 100, "ci95_c": [-9, 4]}, "b": {"pnl": 3, "contracts": 50, "ci95_c": [-5, 8]}}
    assert quick_gate(bad) is not None
    assert quick_gate(unclear) is None
    assert quick_gate({"a": {"pnl": 0, "contracts": 0}}) is not None


def test_walk_forward_verdict():
    from kalshi_lab.validate import verdict
    good = {f"wf-2026-0{i}": {"pnl": 5 if i != 3 else -1} for i in range(1, 6)}
    good.update(POOLED={"pnl": 20, "ci95_c": [0.5, 3.0]}, **{"POOLED-lat2x": {"pnl": 4}})
    assert verdict(good) == "promising"
    bad = dict(good, POOLED={"pnl": -20, "ci95_c": [-3.0, -0.2]})
    assert verdict(bad) == "reject"
    meh = dict(good, POOLED={"pnl": 5, "ci95_c": [-1.0, 3.0]})
    assert verdict(meh) == "inconclusive"


def test_backfill_synthetic_depth_uses_configured_depth():
    ev = [market(ts=1), Trade(2, "M", 600, 2, Side.BUY), Trade(3, "M", 580, 1, Side.SELL)]
    eng = Engine(Strategy(), ev, SimExchange(), has_book=False, synthetic_depth={"X": 40}).run()
    b = eng.ctx.books["M"]
    assert b.ask_qty(600) == 40 and b.bid_qty(580) == 40


def test_lockbox_windows_and_verdict(monkeypatch):
    from datetime import datetime, timezone
    import kalshi_lab.validate as v
    monkeypatch.setattr(v, "backfill_days", lambda s: ["2026-01-01", "2026-09-30"])
    monkeypatch.setattr(v, "recorded_range", lambda s: None)
    lb = v.LOCKBOX_START
    for stage in ("smoke", "quick", "full"):
        assert all(r["end"] <= lb for r in v.plan(stage, ["X"], fits=True)), stage
    lock = v.plan("lockbox", ["X"], fits=True)
    assert lock and all(r["start"] >= lb and r["fit_until"] == lb for r in lock)
    assert v.lockbox_verdict({"POOLED": {"pnl": 5, "contracts": 10, "ci95_c": [0.2, 3]}}) == "strong pass"
    assert v.lockbox_verdict({"POOLED": {"pnl": 5, "contracts": 10, "ci95_c": [-1, 3]}}) == "pass"
    assert v.lockbox_verdict({"POOLED": {"pnl": -1, "contracts": 10, "ci95_c": [-3, 1]}}) == "fail"


def test_lockbox_rolls_monthly():
    from datetime import datetime, timezone
    from kalshi_lab.validate import lockbox_start_for
    u = lambda *a: datetime(*a, tzinfo=timezone.utc)
    assert lockbox_start_for(u(2026, 10, 13, 21)) == u(2026, 9, 1)
    assert lockbox_start_for(u(2026, 10, 31, 23, 59)) == u(2026, 9, 1)
    assert lockbox_start_for(u(2026, 11, 1)) == u(2026, 10, 1)
    assert lockbox_start_for(u(2027, 1, 5)) == u(2026, 12, 1)


def test_strategy_folder_ledger_budget_and_tamper_detection(tmp_path, monkeypatch):
    import json
    import kalshi_lab.strategy_dir as sd
    monkeypatch.setattr(sd, "STRATEGIES", tmp_path)
    monkeypatch.setattr(sd, "LEDGER", tmp_path / "_ledger")
    f = tmp_path / "demo"
    f.mkdir()
    (f / "config.json").write_text(json.dumps({"slug": "demo", "series": ["X"]}))
    (f / "strategy.py").write_text("x = 1\n")
    assert sd.folder_for(str(f)) == f.resolve()
    assert sd.load_config(f)["budget"]["full_tests"] == 3
    for rec in ({"stage": "full", "job": "j1", "verdict": "inconclusive"}, {"stage": "full", "job": "j2", "crashed": True}):
        r = sd.ledger_append("demo", rec)
        sd.append_result(f, r)
    assert sd.count_runs(f, "full") == 1          # crashed runs don't use budget
    for lb in ("2026-08-20T00:00:00+00:00", "2026-09-01T00:00:00+00:00"):
        sd.append_result(f, sd.ledger_append("demo", {"stage": "lockbox", "job": lb, "verdict": "fail", "lockbox_start": lb}))
    assert sd.count_runs(f, "lockbox", "2026-09-01T00:00:00+00:00") == 1  # one lockbox run per period
    assert sd.count_runs(f, "lockbox", "2026-10-01T00:00:00+00:00") == 0 and sd.count_runs(f, "lockbox") == 2
    assert [h["lockbox_start"][:10] for h in sd.family_lockbox_history("demo")] == ["2026-08-20", "2026-09-01"]
    assert sd.ledger_ok("demo") and sd.results_match_ledger(f)
    # an agent editing its own results.json is detected, and doesn't change budgets
    res = json.loads((f / "results.json").read_text())
    res["runs"][0]["verdict"] = "promising"
    (f / "results.json").write_text(json.dumps(res))
    assert not sd.results_match_ledger(f)
    # editing the ledger itself breaks the hash chain
    led = tmp_path / "_ledger" / "demo.jsonl"
    led.write_text(led.read_text().replace('"inconclusive"', '"promising"'))
    assert not sd.ledger_ok("demo")
    # code fingerprint changes when strategy code changes
    h1 = sd.code_hash(f)
    (f / "strategy.py").write_text("x = 2\n")
    assert sd.code_hash(f) != h1


def test_budget_can_only_be_raised_by_user_grant(tmp_path, monkeypatch):
    import json
    import kalshi_lab.strategy_dir as sd
    monkeypatch.setattr(sd, "STRATEGIES", tmp_path)
    monkeypatch.setattr(sd, "GRANTS", tmp_path / "_budgets.json")
    f = tmp_path / "demo"
    f.mkdir()
    (f / "config.json").write_text(json.dumps({"slug": "demo", "series": ["X"], "budget": {"full_tests": 100}}))
    assert sd.load_config(f)["budget"]["full_tests"] == 3          # agent's own increase is ignored
    (f / "config.json").write_text(json.dumps({"slug": "demo", "series": ["X"], "budget": {"full_tests": 1}}))
    assert sd.load_config(f)["budget"]["full_tests"] == 1          # lowering is allowed
    (tmp_path / "_budgets.json").write_text(json.dumps({"demo": {"full_tests": 6}}))
    assert sd.load_config(f)["budget"]["full_tests"] == 6          # user grant wins
