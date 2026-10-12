# kalshi-lab

Record Kalshi 15-minute markets (KXBTC15M, KXETH15M, KXGOLD15M), backtest strategies against the
recorded order books, then promote the same strategy class to paper and live trading.

```
recorder ──► ~/kalshi-data/raw  (zstd JSONL, raw messages + local receive time)
backfill ──► ~/kalshi-data/backfill  (REST trades + 1m spot candles, no order books)
                  │
                  ▼
        Source (Recorded | Backfill | Live) ─► Engine ─► Strategy ─► ctx.buy/sell/cancel
                                                 │
                              SimExchange (backtest, paper)  |  KalshiExchange (live)
```

## Setup

Credentials live outside the repo: `.env` points at `~/.kalshi/kalshi.pem` (chmod 600).
The venv is symlinked to `~/.venvs/kalshi-lab` and data goes to `~/kalshi-data` because iCloud-synced
folders break things (iCloud hides `.pth` files, offloads source files, and would upload GBs of data).
The project lives in ~/Downloads/kalshi, which is not synced.

```
uv sync
uv run pytest
```

## Commands

```
# Record (runs in tmux session `kalshi-rec`; restarts itself on crash)
tmux new -d -s kalshi-rec ./scripts/run_recorder.sh
pkill -TERM -f "kalshi-lab record"            # restart to pick up code changes (loop survives)

# Backfill REST history: Kalshi trades (~3s, ~0.2MB per market) + Binance 1s spot (~10s/day)
uv run kalshi-lab backfill --series KXBTC15M --days 30

# Backtest
uv run kalshi-lab backtest strategies/fair_value.py --source recorded --hours 6
uv run kalshi-lab backtest strategies/fair_value.py --source backfill --start 2026-09-01 --end 2026-09-08
uv run kalshi-lab backtest strategies/quoter.py:Quoter -p half_spread=40 --latency-ms 300
uv run kalshi-lab backtest strategies/fair_value.py --source backfill --sweep edge=30,60,100 --sweep min_tau=20,120

# Promote
uv run kalshi-lab paper strategies/fair_value.py            # live data, simulated fills
uv run kalshi-lab live  strategies/fair_value.py --dry-run  # live data, logs the orders it would send
uv run kalshi-lab live  strategies/fair_value.py --confirm  # real orders
touch ~/kalshi-data/KILL                                    # paper/live: cancel everything and halt

# Dashboard: run backtests, sweeps, and inspect results (equity, per-market PnL, fills on price charts)
uv run kalshi-lab dashboard          # http://localhost:8501

# Research / checks
uv run python scripts/model_vs_market.py KXBTC15M 30  # spot model vs market Brier score by horizon
uv run python scripts/favorites.py KXBTC15M           # favorite-longshot bias, split in/out of sample
uv run python scripts/markouts.py KXBTC15M 48         # do resting orders make money after fills?
uv run python scripts/decompose.py results/<run>      # a run's PnL: edge at fill, adverse selection, carry
uv run python scripts/calibration.py KXBTC15M 30   # market price vs realized outcome by time-to-close
uv run python scripts/check_books.py KXBTC15M 2    # replayed books vs Kalshi's own top-of-book
```

Results go to `results/<name>-<time>/`: `summary.json`, `fills.csv`, `markets.csv` (per-market PnL).

## Writing a strategy

Copy `strategies/template.py`. A strategy is a class with optional hooks
(`on_start`, `on_market`, `on_book`, `on_trade`, `on_spot`, `on_timer`, `on_fill`, `on_settle`, `on_end`)
and a `params` dict. `ctx` gives market data (`active_markets`, `book`, `spot`, `seconds_left`),
account state (`position`, `open_orders`, `cash`) and trading (`buy`, `sell`, `cancel`, `cancel_all`).

Conventions: prices are YES mills (0–1000); `sell` YES is the same as buying NO; negative position = long NO.
Prices are snapped to Kalshi's tick grid ($0.001 below 0.10 and above 0.90, $0.01 between).

`strategies/models.py` has the settlement math: YES iff the 60s average of CF Benchmarks BRTI before
close ≥ the 60s average before open (the market's `strike`). `fair_value.py` prices that from composite
spot + EWMA vol, including the partially-fixed average inside the last minute; `quoter.py` is a
minimal inventory-skewed market maker on the same fair value.

## Simulation model (what to trust)

* **Latency**: orders/cancels arrive `--latency-ms` after submission and match the book at arrival.
* **Taking** walks displayed levels; liquidity we take is remembered until that level disappears.
* **Resting orders** join the back of the queue and fill only on trades at/through our price.
  Cancels ahead of us are ignored → maker fills are a *lower bound*.
* **Fees**: taker `ceil(0.07·C·P·(1−P))` to the cent; makers free on `quadratic` series.
* **Backfill mode** has no order book: the last taker-buy price is the ask, the last taker-sell the bid,
  and spot is 1-minute candles. Good for coarse, long-horizon sanity checks; don't trust fill-sensitive
  results from it. Use recorded data for that.
* `--queue-frac` sets where resting orders join the queue (1.0 back, 0.5 halfway): run both to bracket.
* Use `TIF.POST` (post-only) for maker strategies: crossing orders are rejected instead of paying taker fees.
* Market impact of our own orders on other participants is not modelled.

## Promotion checklist

1. Backtest on recorded data across days you didn't tune on; check `t_stat`, drawdown, fees vs edge.
2. Re-run at 2–3× latency. An edge that disappears at 300ms is a latency race you'll lose live.
3. Paper trade for at least a few hundred markets; compare paper fills/PnL to a backtest of the same period.
4. `live --dry-run` to eyeball real order payloads.
5. `live --confirm` with the default tight limits (5/order, 20/market, $25 max loss), then scale slowly.

Live notes: orders use the V2 endpoint (`POST /portfolio/events/orders`, `exchange_index=-1`
auto-routes: these series live on exchange shard 2). Fills come from the private `fill` websocket.
Positions held before the run starts aren't loaded into the engine's portfolio.

## Running on a server (recommended)

A laptop sleeps and drops recording/paper trading. Run the recorder and paper trader on a small
always-on Linux box in **AWS us-east-1** (closest to Kalshi; ~$10-20/month, e.g. t4g.small, 30 GB disk):

```
deploy/push.sh ubuntu@<server-ip>        # copies code + key, installs uv/chrony, starts systemd services
deploy/dashboard.sh                      # server dashboard in your browser (http://localhost:8502)
deploy/pull_data.sh                     # download all data from S3 + results from the server
```

Services (`kalshi-recorder`, `kalshi-paper`, `kalshi-dashboard`) restart on failure and on boot; logs in
`~/kalshi-data/logs/`. Measured from a home connection: Kalshi feed ~90 ms, OKX gold feed ~215 ms
(OKX's engine is in Asia); from us-east-1 Kalshi drops to a few ms.

## Testing a new strategy

```
uv run kalshi-lab test strategies/my_idea.py --series KXETH15M [-p key=value ...]
```

1. syncs your code to the server (services keep running),
2. **smoke** (~1 min, foreground): last 2h of recorded books (or 6h of backfill). Fails fast if the strategy
   crashes, never trades, or gets rejected by risk limits,
3. queues **quick** (~1-10 min: last 3 days of backfill + 6h of recorded books; clearly negative stops here) and
   **full**: a monthly walk-forward through the engine (strategies with a `fit()` classmethod are refit before each
   month on earlier data only), the last 3 months at 2x latency, and all recorded books; months run in parallel.

Tests run on the laptop by default (the server's burstable CPU is ~30x slower once throttled) and push results
to the server. Data comes from S3 (`src/kalshi_lab/storage.py`); the trading server keeps only recent recordings. **Decisions come from engine results only**; research scripts
(`research/`) are for screening ideas.

Adding a market: one entry in `src/kalshi_lab/recorder/config.py` (`MARKETS`), then redeploy.
Paper trading: `kalshi-lab paper-start <registry-id>` / `paper-stop` / `paper-list` (template unit `kalshi-paper@<id>`).

`uv run kalshi-lab jobs` lists jobs; the dashboard's **Validation jobs** panel shows each stage's report card
(PnL, contracts, PnL/contract with a 95% CI bootstrapped over markets, days positive) and a verdict:
**promising** (both halves > 0, CI above 0, survives 2x latency), **reject**, or **inconclusive**.
Backfill history extends itself daily on the server (00:30 UTC).
