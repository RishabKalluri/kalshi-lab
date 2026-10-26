# kalshi-lab: how the system fits together

*Snapshot as of 2026-09-30. Diagrams are Mermaid; they render in VS Code's Markdown preview and on GitHub.*

kalshi-lab records Kalshi's 15-minute crypto and gold markets, replays that history to test trading
strategies, and promotes the ones that hold up to paper trading and then (with your go-ahead) live trading.
The same strategy code runs in every mode.

---

## 1. The big picture

```mermaid
flowchart LR
    subgraph EXT[Outside world]
        K[Kalshi API + websocket]
        X[Exchanges: Coinbase, Kraken,<br/>Bitstamp, OKX]
        H[History APIs: Kalshi historical,<br/>Binance 1s, OKX, Coinbase]
    end

    subgraph SRV[Server: AWS EC2, Virginia, always on]
        REC[Recorder]
        BF[Nightly backfill]
        PAPER[Paper trader<br/>kalshi-paper@eth-volfav]
        DASH[Dashboard]
        RAW[(raw recordings<br/>~/kalshi-data/raw)]
        HIST[(history<br/>~/kalshi-data/backfill)]
        RES[(results/)]
    end

    subgraph LAP[Your laptop: M2, fast]
        TEST[Test worker:<br/>smoke / quick / full]
        TUN[Dashboard tunnel]
        YOU[You + Claude, via chat]
    end

    K --> REC
    X --> REC
    REC --> RAW
    H --> BF --> HIST
    K --> PAPER
    X --> PAPER
    PAPER --> RES
    RAW -. pulled .-> TEST
    HIST -. pulled .-> TEST
    TEST -. pushes results .-> RES
    RES --> DASH
    DASH --> TUN --> YOU
    YOU --> TEST
```

| Machine | Runs | Why there |
|---|---|---|
| **Trading server** (`ssh kalshi`, EC2 m7g.large, us-east-1, 2 full vCPU / 8 GB, static IP 44.219.216.251, ~$66/mo with disk and IP; moved from Lightsail 2026-10-26, whose burst credits ran out) | recorders (crypto; weather, sports and alts in their own units), paper + live trading, NFL paper trading (`kalshi-nflpaper.timer`, /srv/nfl-q4), dashboard, hourly S3 upload | Must run 24/7; light work. Kalshi feed arrives in ~14 ms (vs ~90 ms from home). |
| **Research server** (`ssh kalshi-research`, EC2 r8g.large, `deploy/research.sh start`; stops itself after 30 idle min) | tests (worker + `kalshi-sandbox`), the official ledger, nightly and one-off downloads (`systemd-run --unit=kalshi-data-<name>` keeps it awake), strategy agents, research screens | CPU-heavy work; agents' code is sandboxed and can't read lockbox data. |
| **S3** | all data (`src/kalshi_lab/storage.py`) | The copy both servers pull from. |
| **Laptop** | Claude Code, deploys, the dashboard tunnel | No tests or data jobs. |

You can turn the laptop off at any time: recording and paper trading keep going on the server.

---

## 2. Data: what we collect and why

```mermaid
flowchart TB
    subgraph LIVE[Recorded live, from Sep 28]
        B[Kalshi order books, BTC/ETH/SOL/gold:<br/>every change + every trade<br/>+ weather from Oct 13: rain + 10 city highs]
        S[Spot prices: Coinbase, Kraken,<br/>Bitstamp for BTC/ETH/SOL; OKX for gold]
        M[Market info + settlements]
    end
    subgraph PAST[Downloaded history backfill]
        T[Kalshi trades + settlements<br/>BTC, ETH: Dec 2025 to now; SOL: Jan 2026 to now;<br/>XRP: Feb 11, DOGE: Mar 19 to now;<br/>~150-market samples of 38 other series Jan-Aug 2026]
        P[Binance 1-second BTC/ETH/SOL,<br/>OKX 1-minute gold]
        F[Order flow per second, BTC/ETH/SOL:<br/>Binance spot + OKX perpetuals, Dec 2025 to now]
    end
    LIVE --> R1[Realistic fills incl. queue position:<br/>needed for market makers]
    PAST --> R2[Months of history:<br/>needed for statistical confidence]
```

- **Why record at all?** Kalshi's API has past *trades* but not past *order books* (who was bidding and
  asking, and how much). Order books only exist if you record them as they happen.
- **Why backfill?** Recording gives realism but only from the day you start; downloaded history gives
  months of markets. Taker strategies (like ETH VolFavorite) are fine on trade history: we measured that
  trade prices match the real book on average (no bias).
- **Format:** compressed zstd JSON lines, one file per stream per hour (recordings) or per market/day
  (history). Raw messages are stored untouched and normalized when replayed.
- **Size:** ~1.8 GB/day recorded; ETH's 9.5 months of history is ~1 GB.

- **Order flow** (`backfill/flow/`, added Oct 1): per-second taker buy/sell volume from Binance spot and
  OKX perpetuals (OKX instead of Binance futures because Binance's API is blocked from US IPs, which
  would make it unusable live). Research only so far: not recorded live and not replayed by the engine.
  Loader: `kalshi_lab.data.flow`.

**One config table** (`src/kalshi_lab/recorder/config.py → MARKETS`) says, per Kalshi series, which spot
feeds track its settlement index, which public history to download, and how it settles (60-second average
for crypto, a single 1-minute close for gold). Adding a market = one entry there.

---

## 3. The trading engine (backtest = paper = live)

```mermaid
flowchart LR
    SRC[Event source<br/>Recorded / Backfill / Live] --> ENG[Engine<br/>time-ordered events,<br/>1s timer]
    ENG --> CTX[ctx: books, spot, positions,<br/>buy/sell/cancel, size]
    CTX <--> STRAT[Your strategy class<br/>on_timer, on_trade, on_book, fit...]
    CTX --> SIZER[Sizing<br/>1% of equity per order,<br/>5% max per market]
    SIZER --> RISK[Risk limits<br/>max order, position, loss,<br/>KILL file]
    RISK --> EXCH{Exchange}
    EXCH -->|backtest + paper| SIM[Simulated exchange<br/>latency, queue position,<br/>fees, tick sizes, post-only]
    EXCH -->|live, off until you say| KAL[Kalshi V2 orders<br/>+ private fill feed]
    SIM --> FILLS[Fills -> portfolio -> settlement PnL]
    KAL --> FILLS
```

- **Strategies only decide *what* to trade.** How much comes from the sizing layer, the same for every
  strategy: risk 1% of equity per order, never more than 5% in one market. Kelly sizing exists but isn't
  used on unproven edges.
- **Backfill books** show a configured depth per market (`MARKETS[...].book_depth`, the 25th percentile of real
  recorded best-price depth), because history has trades but no books and a trade's size understates depth.
- **The simulated exchange** is deliberately conservative: orders arrive after a latency delay and see the
  book at arrival; resting orders join the back of the queue; Kalshi's real fees
  (`ceil(0.07·C·P·(1−P))` for takers, zero for makers on these series) and tick sizes apply; orders that
  miss are logged as "missed", not silently dropped.
- **Live trading** is built (Kalshi's V2 order endpoint, private fill websocket, dry-run mode) but has never
  sent a real order. It needs your explicit go-ahead.

---

## 4. Testing a strategy: the validation pipeline

```mermaid
flowchart LR
    IDEA[Idea<br/>you describe it in chat] --> RESEARCH[Research<br/>screening only]
    RESEARCH --> CODE[Strategy file]
    CODE --> SMOKE{Smoke<br/>~1 min}
    SMOKE -->|fails| FIX[fix or drop]
    SMOKE -->|passes| QUICK{Quick<br/>~1-10 min}
    QUICK -->|clearly negative| REJ[Rejected at quick]
    QUICK -->|unclear or positive| FULL{Full<br/>walk-forward<br/>~25-60 min}
    FULL -->|reject| REJ2[Rejected]
    FULL -->|inconclusive| MORE[more data / rethink]
    FULL -->|promising| LIVEQ[Live decision]
    QUICK -. paper can start here, in parallel .-> PAPER[Paper trading]
    PAPER --> LIVEQ
    LIVEQ -->|your go-ahead| LIVE[Live: small size,<br/>stop rules]
```

| Stage | What it runs | Gate |
|---|---|---|
| **Smoke** | last 2 h of recorded books (or 6 h of history) | must run, trade, and not get rejected by risk limits |
| **Quick** | last 3 days of history + last 6 h of recorded books | clearly negative (every run loses *and* a 95% CI entirely below 0) → stop |
| **Full** | **walk-forward**: one backtest per month, strategy refit before each month on earlier data only (`fit()` hook); the last 3 months again at 2× latency; all recorded books | **promising** = pooled 95% CI above 0, ≥60% of months positive, still positive at 2× latency; **reject** = CI below 0 or <40% of months positive |
| **Paper** | live data, simulated money, 24/7 on the server | checks live execution matches the sim (signal rate, fill rate, fill prices) |
| **Live** | real money, small size, stop rules set in advance | needs a finished Full test **and** enough paper **and** your go-ahead |

Rules we settled on:
- **Decisions come from engine results only.** Research scripts simplify execution and are for screening.
  (A +2.2¢ research result was −0.2¢ in the engine until the entry timing was fixed.)
- **Paper can start once Quick passes** and run alongside the Full test, since it risks no money.
- **Paper doesn't prove an edge; the walk-forward does.** With ~15 traded markets a day, even a real
  +2¢ edge looks negative about a third of the time after a week of paper. Paper's job is checking that
  live trading behaves like the simulation (about a week is enough for that).

How a test runs mechanically:

```mermaid
sequenceDiagram
    participant C as Claude (chat)
    participant L as Laptop
    participant S as Server
    C->>L: kalshi-lab test strategies/x.py --series KXETH15M
    L->>S: pull history + recent recordings (rsync)
    L->>S: sync code
    L->>L: smoke (foreground)
    L->>L: queue quick + full for the laptop worker
    loop every 30s while running
        L->>S: push job progress + results
    end
    S-->>C: dashboard shows report card + verdict
```

---

## 4b. Agent-driven strategy development

Each strategy is developed by its own agent (`/develop-strategy [market] [idea]`, a forked skill) in its own
folder, and the agent drives the pipeline itself:

```mermaid
flowchart LR
    A[/develop-strategy KXSOL15M/] --> B[read SYSTEM.md, other NOTES.md,<br/>rejected ideas, research tools]
    B --> C[kalshi-lab new slug<br/>hypothesis written first]
    C --> D[research + implement]
    D --> E{smoke}
    E --> F{quick}
    F -->|clearly negative| D
    F --> G{full<br/>budget 3}
    G -->|not promising: log learning,<br/>change one thing| D
    G -->|promising| H{lockbox<br/>rolling monthly}
    H -->|fail| R[rejected]
    H -->|pass| P[paper-start]
```

```
strategies/<slug>/  strategy.py · config.json · NOTES.md (learnings, kept current) · results.json · research/
strategies/_template/  copied by `kalshi-lab new`     strategies/_archive/  older experiments + legacy registry
```

**The lockbox:** the most recent 4-9 weeks are held out: data from the 1st of the previous month on, rolling on
the 1st of each month (the month leaving it becomes development data). Smoke/quick/full only use earlier
"development" data; after a promising full test a strategy gets **one** lockbox run per period (pass = profitable,
strong pass = CI above 0, fail = that version is rejected). Versions of an idea each get a run; the dashboard
shows the family's lockbox history. This is the defense against overfitting by iteration.

**Anti-cheating layers:** (1) every pipeline run is appended to a hash-chained ledger outside the strategy's
folder (`results/_ledger/<slug>.jsonl`); budgets and gates read only the ledger, and the dashboard flags a
results.json that disagrees; (2) the lockbox only opens for the exact code (fingerprint) that earned the
promising verdict; (3) a hook blocks subagents from editing records, grading code, infrastructure, other
strategies, credentials or the server, and backtests into the lockbox are refused; (4) before anything goes
live, `kalshi-lab audit <slug>` independently re-runs the full test and lockbox and compares to the ledger.

## 5. Paper trading

- One systemd **template** service on the server: `kalshi-paper@<id>`, configured by
  `deploy/paper/<id>.json` (strategy file, series, params).
- `kalshi-lab paper-start <id>` / `paper-stop <id>` / `paper-list` (run from the laptop; Claude runs these).
- On start, strategies preload the last 4 hours of recorded prices, so restarts need no warm-up.
- Each run writes a timestamped results folder, saved every 5 minutes, including `orders.csv`
  (every order: filled, partly filled, or missed).
- Priority: recorder and paper traders run at high CPU priority, tests and downloads at low priority.
- Ubuntu's automatic security updates stay on but no longer restart our services.

---

## 6. The dashboard

Open **http://localhost:8501** (a tunnel to the server; `deploy/dashboard.sh` restarts it if needed).

```
┌ Strategies ───────────────────────────────────────────────────────────────┐
│ ● Recorder  ● Paper: eth-volfav  ● Test worker  ● Market data  ● CPU        │
│ ▸ Data downloads (progress, time running, time left, which strategy uses it)│
├─────────────────────────────────────────────────────────────────────────────┤
│ ETH VolFavorite                                           paper trading     │
│ What it does: ...                                                           │
│ Running now: paper 12/~350 markets · 2h 10m · waiting on data 48% ~30m left │
│ [✓ Idea][✓ Research][✓ Smoke][✓ Quick][✓ Full test][◉ Paper][○ Live]  ← tabs│
│   What this stage checks · result · numbers · runs table                   │
│ Next: ...                                                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│ ▸ Rejected ideas (why each failed)                                          │
└─────────────────────────────────────────────────────────────────────────────┘
  Other pages: Runs (every backtest/paper run in detail) · New backtest (form)
```

Stage marks: ✓ done · ◐ partly done · ◉ current · ○ not yet. Stage text, descriptions and recorded
numbers come from each strategy folder (config.json, results.json, NOTES.md); live status (tests, paper,
downloads) is read automatically.

---

## 7. Strategies so far

| Strategy | Status | One line |
|---|---|---|
| **ETH VolFavorite** | **Live as eth-volfav-kelly (quarter Kelly, $1,050) since Oct 21**; v1 live Oct 8-14, v2 live Oct 14-21 (+$52.32); v1 + v2 paper alongside; XRP port on paper | Buy the favourite late in the window when implied vol is well above a forecast. Kelly sizing uses a calibrated win probability (model edge shrunk ~0.4) and skips trades whose edge doesn't cover the price. |
| BTC Ladder Relative Value | Research | Quote thin hourly BTC range markets around the fair value implied by the liquid above/below ladder. Promising signal (+1.3¢ when takers overpay); needs recorded books. |
| Gold Maker | Rejected (parked) | Zero-fee market making on gold; break-even in backtest, loses live to faster traders. |
| BTC Spread Maker | Rejected (parked) | Back-of-queue fills get picked off. |
| BTC spot fair value, BTC vol, gold taker, favorite-longshot | Rejected | The BTC market prices these correctly; details on the dashboard. |

Lessons that shaped the system:
1. BTC's 15-minute market is efficient; ETH's is less so. Same test, opposite results.
2. **Entry timing can flip a strategy's sign**: checking every second and entering on the first crossing
   buys momentary spikes; checking at fixed times doesn't.
3. Research ≠ engine, and backtest ≠ live, so every step verifies the one before it.

---

## 8. Commands (Claude runs these for you)

```
/develop-strategy KXSOL15M                                 # (in Claude Code) an agent develops a new strategy
uv run kalshi-lab new <slug> --series KXSOL15M             # new strategy folder from the template
uv run kalshi-lab test <slug> --skip-smoke --stages full --wait   # one pipeline stage (smoke/quick/full/lockbox)
uv run kalshi-lab data KXSOL15M                            # history available; development vs lockbox split
uv run kalshi-lab audit <slug>                             # independent re-run vs the ledger (before live)
uv run kalshi-lab jobs                                     # job status
uv run kalshi-lab backtest <strategy.py> --source backfill --start ... --end ...
uv run kalshi-lab paper-start <id> | paper-stop <id> | paper-list
uv run kalshi-lab backfill --series KXETH15M --days 30     # download history
deploy/push.sh kalshi          # deploy code to the server (paper traders keep running)
deploy/pull_data.sh            # download all data from S3 to the laptop
deploy/dashboard.sh            # (re)open the dashboard tunnel
touch ~/kalshi-data/KILL       # on the server: halt paper/live trading and cancel everything
```

---

## 9. Where things live

```
kalshi/
├── SYSTEM.md, README.md
├── src/kalshi_lab/
│   ├── recorder/     config.py (MARKETS table) · kalshi.py · spot.py · sink.py (zstd logs) · main.py
│   ├── data/         backfill.py (history downloads) · flow.py (order-flow loader) · normalize.py · source.py (replay)
│   ├── core/         types.py · book.py · fees.py · portfolio.py · risk.py
│   ├── sim/          exchange.py (simulated matching)
│   ├── live/         run.py (paper/live runner) · exchange.py (real orders) · source.py · history.py
│   ├── engine.py · strategy.py (Strategy + ctx) · sizing.py · report.py · backtest.py
│   ├── validate.py (smoke/quick/full/lockbox, audit) · strategy_dir.py (folders, ledger) · jobs.py · remote.py
│   ├── paper_ctl.py (paper-start/stop) · auth.py · rest.py
│   └── dashboard/    app.py · pipeline.py (Strategies page) · background.py
├── strategies/       <slug>/ (strategy.py, config.json, NOTES.md, results.json) · IDEAS.md (backlog) · _template/ · _archive/
├── research/         screening scripts (walk_forward.py, build_dataset.py, ...) · data/
├── scripts/          one-off checks (check_books, markouts, decompose, ...)
├── .claude/          skills/develop-strategy/ (SKILL.md, reference.md) · hooks/strategy_agent_guard.py · settings.json
├── deploy/           server_setup.sh · push.sh · pull_data.sh · dashboard.sh · paper/<id>.json
├── tests/            unit tests (sim, engine, sizing, pipeline gates)
└── results/          every run's summary.json, markets.csv, fills.csv, orders.csv, timeline; _jobs/
Data (outside the repo, not iCloud-synced): ~/kalshi-data/{raw, backfill, logs}
Credentials: ~/.kalshi/kalshi.pem + .env (KALSHI_KEY_ID)
```

---

## 10. Open items

- **Monthly model refits** (Oct 14): `research/refit_live.py` runs in the research server's nightly job and acts on the
  1st (UTC): refits eth-volfav2 / xrp-volfav on all earlier markets, sanity-checks, uploads to `s3://.../models/`; the
  trading server pulls hourly (`kalshi-lab models-pull`) and live/paper traders re-read the file without a restart.

- **Category survey (Oct 13, `research/category_survey.py`)**: scored every trade in ~150 settled markets per
  series (38 series, Jan-Aug 19) against settlement. Weather takers overpay consistently (-0.3 to -1.6¢/contract,
  cheap brackets, no maker fees); BTC/ETH 15M ~0; sports noisy, some with informed in-game takers. Next: weather
  books are recording (maker test possible ~early Nov); a weather forecast-vs-price taker strategy can test on
  history now; sports break-period screen (`research/sports_breaks.py`) to run on the research server.
- **XRP/DOGE 15M** (Oct 13): history downloading on the research server (added to nightly); next: VolFavorite on them.

- **SOL 15-minute added Oct 1** (about 1/3 of ETH's volume, so likely less efficient): recording books;
  history back to Jan 9, 2026 downloading. Next: recalibrate its book depth from a day of recordings, then
  test VolFavorite-style ideas on it.

- **Rotate the Kalshi API key** (the current one was pasted into chat) and **fund the account**
  (balance showed −$42.35) before any live trade.
- ETH VolFavorite: ~1 week of paper to check execution, then a $200 live-trial decision.
- BTC 12-month control test (download running); rerun ETH's August month now that its history gap is fixed.
- Optional: a dedicated-CPU server (e.g. Hetzner dedicated vCPU, ~$15-25/mo) so tests can run overnight.
- Deferred: Kalshi 1-minute bid/ask candles for more realistic backfill prices; recording the hourly
  BTC ladder markets for the relative-value idea.
