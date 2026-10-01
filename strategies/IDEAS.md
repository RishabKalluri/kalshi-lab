# Strategy ideas backlog

Ideas worth trying, roughly best-first within each section. Anyone (the user, the main session, strategy
agents) can add to it. When a `/develop-strategy` agent takes an idea, it marks it `→ taken: <slug>` and
links the folder; when the idea is finished, move it to **Tried**, with the outcome in one line. Detailed
results live in each strategy's `NOTES.md` and in `_archive/registry.json`.

Each idea: **what**, *why it might work / who loses*, the data it needs, and leads.

## Ready to try (data exists)

- **Last-minute momentum in ETH.** In `research/settlement_manipulation.py`, 59% of large (2σ)
  settlement-minute ETH moves continued *away* from the strike (BTC 51%, SOL 55%). Not yet compared
  with other minutes, so it could be general momentum. If it's real, the favourite at T−60s is
  underpriced. Check it against the other minutes before building anything.
- **VolFavorite on SOL** (port of `eth-volfav`). SOL's market has about ⅓ of ETH's volume, so it's
  probably less efficient. Waits for the SOL Kalshi history download (server tmux `backfill-sol`) and a
  `book_depth` recalibration from recorded SOL books.
- **BTC leads ETH/SOL.** BTC spot (or BTC's Kalshi market) moves first; ETH/SOL Kalshi quotes reprice
  late. Trade ETH/SOL markets on fresh BTC moves. *Slow retail quotes on the thinner markets.* Data:
  spot 1s for all three, Kalshi trades.
- **Cross-market consistency (ETH vs BTC Kalshi).** The two markets' implied probabilities should be
  consistent given the BTC–ETH correlation; when ETH's is far off given BTC's, fade it.
- **Kalshi trade-size signals.** Big Kalshi taker prints (top 1% size) in the last minutes: informed (copy)
  or fat-finger/overreaction (fade)? Data: Kalshi trades with aggressor side (backfill).
- **Time-of-day and weekend regimes.** Thin hours (weekends, 00–08 UTC) may be less efficient; condition
  existing signals on the hour, or find hour-specific biases.
- **Scheduled macro events** (CPI, FOMC, NFP at 8:30/14:00 ET). Vol jumps at known times; does the
  market price the jump properly in the window around the release? Needs an event calendar (public).
- **Round-number strikes.** Markets whose strike sits near a round number (ETH $2,000) may misprice
  barrier-like behaviour (support/resistance, option-pinning flow).

## Needs data or infrastructure first

- **Ladder relative value** (KXBTC ranges vs the KXBTCD above/below ladder): thin range markets quoted
  around the ladder-implied fair value. Needs recorded hourly-ladder books (`research/ladder_rv.py`).
- **Options-implied vol (Deribit DVOL) as the vol forecast** in a VolFavorite-style model. Needs a DVOL
  history download (public API).
- **Order-book imbalance on spot exchanges.** Needs books recorded live from now (free) or bought
  history (Tardis.dev, Kaiko). Only worth it if the trade-flow idea above shows something.
- **Funding / open interest swings** (OKX public metrics) as a regime filter for momentum vs reversal.

## Tried

- **ETH VolFavorite** (`strategies/eth-volfav/`): buy the favourite when implied vol ≫ forecast vol.
  Walk-forward +2.16¢/contract, 6/8 months positive. Now **paper trading**.
- **BTC vol ratio, BTC fair value, BTC favourites (90¢+), BTC maker**: rejected. BTC's 15-minute market
  is efficient.
- **Gold taker and gold maker**: rejected/parked. Gold settles on a key-gated Pyth print, and the OKX proxy
  wasn't good enough.
- **Open-window edge** (`research/open_edge.py`): market isn't slow to price spot vs strike at the open
  (BTC).
- **Settlement manipulation** (`research/settlement_manipulation.py`): no fingerprint of spot pushes
  during the settlement window in BTC/ETH/SOL (the window is the *calmest* minute; no reversal; the
  official index matches Binance within ~0.5 bp). Not a risk worth modelling for now.
- **Order-flow pressure before checkpoints** (`strategies/sol-flow/`, taker on SOL and ETH): parked at
  research. ETH Binance taker imbalance and signed volume (30 s to 5 min) don't predict the move to settlement
  (|r| < 0.03). Following them at the next real Kalshi fill loses about the fee plus spread (≈ −2¢) on SOL and
  on ETH's own market, and no decile comes out positive. SOL's own flow is untested because it isn't downloaded.
