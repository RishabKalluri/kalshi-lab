# develop-strategy reference

All commands run from the repo root with `uv run` (research server: `/srv/kalshi`; data in `/srv/kalshi-data`,
which replaces `~/kalshi-data` below). On the research server, lockbox-dated data files are not readable at all:
when your own scripts list data files, skip dates on/after the lockbox start instead of filtering after reading.

## Commands
| Command | What it does |
|---|---|
| `kalshi-lab data [SERIES...]` | history range, development vs lockbox days, spot sources, recorded books |
| `kalshi-lab pull SERIES...` | laptop only: download the history + recordings for these series from S3 (the research server syncs automatically) |
| `kalshi-lab new <slug> --series S --name N` | create `strategies/<slug>/` from `strategies/_template/` |
| `kalshi-lab test <slug> --stages "" --note "..."` | smoke only (foreground, ~1 min) |
| `kalshi-lab test <slug> --skip-smoke --stages quick\|full\|lockbox --wait --note "..."` | queue a stage on the test worker and wait for its verdict |
| `kalshi-lab jobs` | job queue status |
| `kalshi-lab backtest strategies/<slug>/strategy.py --source backfill --series S --start 2026-05-01 --end 2026-05-08 -p k=v` | ad-hoc debugging run (development dates only!). Writes `results/<name>-<time>/` |
| `kalshi-lab backtest ... --sweep k=1,2,3` | parallel parameter sweep (counts toward overfitting: use sparingly, log it) |
| `python scripts/decompose.py results/<run>` | PnL split into edge at fill, adverse selection, carry |
| `kalshi-lab paper-start <slug>` / `paper-list` | start paper trading after a lockbox pass / list paper traders |

## Data
- **History ("backfill")**: Kalshi trades + settlements per market (`~/kalshi-data/backfill/kalshi/<SERIES>/<close-date>/<ticker>.jsonl.zst`)
  and spot prices (`~/kalshi-data/backfill/spot/<stream>/<date>.jsonl.zst`: Binance 1-second BTC/ETH/SOL, OKX
  1-minute gold, Coinbase 1-minute). BTC and ETH from Dec 2025; SOL from Jan 2026 (check `kalshi-lab data`).
  No order books in history: backtests show `MARKETS[series].book_depth` contracts at the trade price.
- **Order flow** (`~/kalshi-data/backfill/flow/<source>/<date>.parquet`, BTC/ETH/SOL from Dec 2025): per
  second, taker buy and sell volume, trade count, last price (and largest trade, OKX only) for Binance spot
  (`binance_<coin>usdt`) and OKX perpetuals (`okx_<coin>usdtswap`). Load with
  `from kalshi_lab.data.flow import load_flow, flow_sources`. **Research and backtest-in-`fit()` only for now:**
  the engine doesn't replay it and the recorder doesn't stream it live, so a strategy that needs it at trade
  time needs infrastructure (a recorder stream + engine replay). If your flow research is promising, stop
  and report exactly what you need.
- **Recorded books**: every order-book change and trade since late Sep 2026 for BTC/ETH/SOL/gold 15m, plus
  live spot (`~/kalshi-data/raw/...`). These are all inside the lockbox; they're used by the lockbox stage.
- **Research dataset**: `research/build_dataset.py <SERIES>` builds `research/data/<SERIES>.parquet`
  (one row per market × horizon: quotes, next-trade fills, spot, strike, realized vols, implied vol, outcome).
  Filter it to `close < lockbox start` for research.
- **Market config**: `src/kalshi_lab/recorder/config.py` `MARKETS` (spot feeds, settlement type, book depth).
  Settlement: crypto 15m = 60s average of the CF Benchmarks index before close ≥ 60s average before open
  (the `strike`); gold = one Pyth 1-minute close.
- Other Kalshi series (hourly ladders KXBTCD/KXETHD/KXSOLD..., ranges KXBTC/KXETH..., other coins'
  15m markets, non-crypto) can be downloaded, but that's a data request: ask the user.

## Strategy API (src/kalshi_lab/strategy.py)
Prices are YES **mills** (0..1000). `Side.BUY` = buy YES, `Side.SELL` = sell YES (= buy NO).
Hooks (all optional): `on_start(ctx)`, `on_market(ctx, m)`, `on_book(ctx, ticker, book)`, `on_trade(ctx, t)`,
`on_spot(ctx, tick)`, `on_timer(ctx)` (every second), `on_fill(ctx, f)`, `on_settle(ctx, m, pnl)`, `on_end(ctx)`.
`fit(cls, series, until) -> dict` (classmethod): train on data before `until`, return param overrides.
Write anything `fit()` produces under `strategies/<slug>/params/`. That folder is excluded from the code
fingerprint, and the lockbox (and audits) set it aside and refit, so the strategy must not depend on any file in
`params/` that its `fit()` doesn't write itself. Everything else in the folder (outside `research/`) is code: changing
it after a promising full test means rerunning the full test before the lockbox.

`ctx`: `now` (ns), `active_markets(series=None)`, `markets[ticker]` (`MarketInfo`: `open_ts`, `close_ts`,
`strike`, `series`), `book(ticker)` (`best_bid`, `best_ask`, `mid`, `bids()`, `asks()`, `bid_qty(p)`,
`ask_qty(p)`), `spot(series=...)` (median of fresh feeds), `seconds_left(ticker)`, `position(ticker)`,
`open_orders(ticker)`, `cash`, `equity()`, `size(ticker, side, price, prob=None, tif=...)` (contracts from
the sizing policy: never size yourself), `buy/sell(ticker, price, qty, tif=TIF.IOC|GTC|POST, tag=...)`,
`cancel(order)`, `cancel_all(ticker)`, `record(ticker, name, value)` (plotted on the dashboard), `log`,
`spot_history(series, seconds)` (paper/live only: recent spot from recordings, for warm-up).
Helpers to reuse: `strategies/eth-volfav/vol_fit.py` (HAR vol model fit), `strategies/eth-volfav/strategy.py`
(`_Hist` O(1) realized-vol window, implied-vol math), `strategies/_archive/models.py` (settlement-average
probability model, EWMA vol), `strategies/_archive/maker.py` (quoting, protection, post-only).

## Simulation model (what the tests assume)
150 ms order latency (2× = 300 ms in the latency runs); taker orders walk displayed levels; resting orders
join the back of the queue and fill on trades at/through their price; Kalshi fees and tick sizes; orders
after close are rejected; sizing 1% of equity per order unless config says otherwise (`sizing`).

## Files in a strategy folder
- `config.json`: `slug, name, series, class, status (developing|paper|live|rejected|parked), description,
  hypothesis, params (["k=v"] for tests), paper_params, sizing, budget {full_tests, lockbox_runs}, created, next`.
- `results.json`: `{"runs": [{stage, job, started, finished, git, params, note, iteration, windows, cards,
  verdict, gate, crashed}]}`. `cards[run]` = `{pnl, contracts, markets, pnl_per_contract_c, ci95_c,
  days_positive, max_drawdown, ...}`; full/lockbox also have `POOLED` (and `POOLED-lat2x`). Appended by the
  pipeline; read it to decide your next step.
- Run outputs: `results/<job>-<run>/` (`summary.json`, `markets.csv`, `fills.csv`, `orders.csv`,
  `timeline.csv.gz`).

## Verdict rules
- quick: rejected if every run loses and a 95% CI is entirely below 0; otherwise passed.
- full: promising = pooled 95% CI > 0, ≥60% of months positive, positive at 2× latency; reject = CI < 0 or
  <40% of months positive; else inconclusive.
- lockbox: strong pass = profitable with CI > 0; pass = profitable; fail = not profitable (reject the idea).
