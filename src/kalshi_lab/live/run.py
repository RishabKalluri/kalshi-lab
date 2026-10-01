"""kalshi-lab paper|live <strategy> [options]

paper  live market data, simulated fills (SimExchange). Nothing is sent to Kalshi.
live   live market data, real orders. Requires --confirm; add --dry-run to log orders instead.

Touch <data>/KILL (default ~/kalshi-data/KILL) at any time to cancel everything and halt.
"""

import argparse
import logging
import os
import signal
import time
from datetime import datetime
from pathlib import Path

from ..backtest import load_strategy, parse_params
from ..core.fees import Fees
from ..core.risk import RiskLimits
from ..engine import Engine
from ..report import print_summary, save, summarize
from ..sim.exchange import SimExchange
from ..sizing import DEFAULT_MAX_FRAC, DEFAULT_SIZING
from ..sizing import parse as parse_sizing
from ..recorder.config import spot_map
from .source import LiveSource

log = logging.getLogger("run")
NS = 1_000_000_000


class LiveEngine(Engine):
    def __init__(self, *a, status_s: float = 60, kill_file: Path | None = None, out: Path | None = None,
                 meta: dict | None = None, save_s: float = 300, **kw):
        super().__init__(*a, **kw)
        self.status_ns = int(status_s * NS)
        self.kill_file = kill_file
        self._next_status = 0
        self.out, self.meta = out, meta or {}
        self.save_ns, self._next_save = int(save_s * NS), 0

    def _advance(self, t: int):
        super()._advance(t)
        if t >= self._next_status:
            self._next_status = t + self.status_ns
            self._status()
            if self.out and t >= self._next_save:  # keep results fresh for the dashboard during long runs
                self._next_save = t + self.save_ns
                try:
                    save(self, summarize(self), self.out, self.meta)
                except Exception:
                    log.exception("periodic save failed")
            if self.kill_file and self.kill_file.exists() and not self.ctx.halted:
                log.error("KILL file present: halting and cancelling all orders")
                self.ctx.halted = True
                self.ctx.cancel_all()

    def _status(self):
        c = self.ctx
        pos = {t[-14:]: round(q, 2) for t, q in self.portfolio.pos.items() if abs(q) > 1e-9}
        act = c.active_markets()
        tops = {m.ticker[-14:]: (b.best_bid, b.best_ask) for m in act if (b := c.book(m.ticker))}
        spots = {s: c.spot(series=s) for s in c.spot_map}
        realized = sum(p for _, _, p in self.settlements)
        log.info("equity=%.2f settled_pnl=%.2f fees=%.2f fills=%d open_orders=%d pos=%s spot=%s books=%s",
                 self.equity(), realized, self.portfolio.fees, len(self.fills), len(c.open_orders()), pos,
                 spots, tops)


def main(argv=None, mode: str = "paper"):
    p = argparse.ArgumentParser(prog=f"kalshi-lab {mode}", description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("strategy")
    p.add_argument("--series", nargs="+", default=["KXBTC15M"])
    p.add_argument("-p", "--param", action="append")
    p.add_argument("--latency-ms", type=float, default=150, help="paper only: simulated order latency")
    p.add_argument("--timer-ms", type=int, default=1000)
    # Tighter defaults than backtest: this is where real money starts.
    p.add_argument("--max-position", type=float, default=500 if mode == "paper" else 20)
    p.add_argument("--max-order-qty", type=float, default=200 if mode == "paper" else 5)
    p.add_argument("--max-loss", type=float, default=250 if mode == "paper" else 25)
    p.add_argument("--status-s", type=float, default=60)
    p.add_argument("--sizing", default=DEFAULT_SIZING, help="pct:P | fixed:N | risk:DOLLARS | kelly:FRACTION")
    p.add_argument("--bankroll", type=float, default=1000.0 if mode == "paper" else 100.0,
                   help="equity the sizer works from (paper: notional; live: set to what you can afford to lose)")
    p.add_argument("--max-frac", type=float, default=DEFAULT_MAX_FRAC)
    p.add_argument("--out")
    if mode == "live":
        p.add_argument("--confirm", action="store_true", help="required: acknowledge real orders will be sent")
        p.add_argument("--dry-run", action="store_true", help="log order requests instead of sending them")
    a = p.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)

    if mode == "live":
        if not (a.confirm or a.dry_run):
            raise SystemExit("live mode sends real orders: pass --confirm (or --dry-run to only log them)")
        from .exchange import KalshiExchange
        exch = KalshiExchange(dry_run=a.dry_run)
    else:
        exch = SimExchange(latency_ms=a.latency_ms, fees=Fees())

    strat = load_strategy(a.strategy)(**parse_params(a.param))
    risk = RiskLimits(max_position=a.max_position, max_order_qty=a.max_order_qty, max_loss=a.max_loss)
    source = LiveSource(a.series)
    data_root = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent
    sp = Path(a.strategy.split(":")[0])
    name = sp.parent.name if sp.name == "strategy.py" else sp.stem  # strategy folders are named by their slug
    out = Path(a.out or f"results/{mode}-{name}-{datetime.now():%Y%m%d-%H%M%S}")
    meta = {"mode": mode, "strategy": a.strategy, "params": parse_params(a.param), "resolved_params": vars(strat.p),
            "series": a.series, "source": mode, "sizing": a.sizing, "bankroll": a.bankroll,
            "start": datetime.now().astimezone().isoformat(), "end": "(running)", "latency_ms": a.latency_ms}
    from .history import recent_spot
    smap = spot_map(a.series)
    eng = LiveEngine(strat, source, exch, risk=risk, timer_ms=a.timer_ms, status_s=a.status_s,
                     kill_file=data_root / "KILL", spot_map=spot_map(a.series), out=out, meta=meta,
                     sizer=parse_sizing(a.sizing, a.max_frac), cash=a.bankroll, timeline_s=5)

    def stop(*_):
        log.info("stopping...")
        source.stop.set()
    # Strategies can prefill history from the recorder's files instead of warming up after a restart.
    eng.ctx.spot_history = lambda series, seconds: recent_spot(smap.get(series, []), seconds)
    signal.signal(signal.SIGINT, stop)
    signal.signal(signal.SIGTERM, stop)

    log.info("%s: %s on %s, risk=%s", mode.upper(), type(strat).__name__, a.series, risk)
    started = time.time()
    try:
        eng.run()
    finally:
        if mode == "live" and hasattr(exch, "cancel_everything"):
            exch.cancel_everything()
        s = summarize(eng)
        s["wall_s"] = round(time.time() - started, 1)
        meta["end"] = datetime.now().astimezone().isoformat()
        save(eng, s, out, {**meta, "risk": vars(risk)})
        print_summary(s)
        print(f"results: {out}/")


def paper(argv=None):
    main(argv, "paper")


def live(argv=None):
    main(argv, "live")
