# Strategy ideas backlog

Ideas worth trying, roughly best-first within each section. Anyone (the user, the main session, strategy
agents) can add to it. When a `/develop-strategy` agent takes an idea, it marks it `→ taken: <slug>` and
links the folder; when the idea is finished, move it to **Tried**, with the outcome in one line. Detailed
results live in each strategy's `NOTES.md` and in `_archive/registry.json`.

Each idea: **what**, *why it might work / who loses*, the data it needs, and leads.

## Ready to try (data exists)

- **Last-minute momentum in ETH.** → taken: `settle-lockin` (see Tried). In `research/settlement_manipulation.py`, 59% of large (2σ)
  settlement-minute ETH moves continued *away* from the strike (BTC 51%, SOL 55%). Not yet compared
  with other minutes, so it could be general momentum. If it's real, the favourite at T−60s is
  underpriced. Check it against the other minutes before building anything.
- **BTC leads ETH/SOL.** BTC spot (or BTC's Kalshi market) moves first; ETH/SOL Kalshi quotes reprice
  late. Trade ETH/SOL markets on fresh BTC moves. *Slow retail quotes on the thinner markets.* Data:
  spot 1s for all three, Kalshi trades.
- **Cross-market consistency (ETH vs BTC Kalshi).** → taken: `btc-anchor-vol` (vol version; see Tried). The two markets' implied probabilities should be
  consistent given the BTC–ETH correlation; when ETH's is far off given BTC's, fade it.
- **Kalshi trade-size signals.** → taken: `settle-lockin` (see Tried). Big Kalshi taker prints (top 1% size) in the last minutes: informed (copy)
  or fat-finger/overreaction (fade)? Data: Kalshi trades with aggressor side (backfill).
- **Time-of-day and weekend regimes.** → partly screened in `btc-anchor-vol/research/bias_scan.py`; → taken: `us-hours-vol` (see Tried). Thin hours (weekends, 00–08 UTC) may be less efficient; condition
  existing signals on the hour, or find hour-specific biases.
- **Scheduled macro events** (CPI, FOMC, NFP at 8:30/14:00 ET). (8:30 slot as a whole screened in `us-hours-vol` H3: priced correctly; per-event calendar still untested.) Vol jumps at known times; does the
  market price the jump properly in the window around the release? Needs an event calendar (public).
- **Round-number strikes.** Markets whose strike sits near a round number (ETH $2,000) may misprice
  barrier-like behaviour (support/resistance, option-pinning flow).

- **SOL version of the open reversal fade.** Same rule as `eth-overreact` on KXSOL15M: research +5.6¢ (t 4.0), 7/8
  months, May–Aug still +2.6..+3.7¢ (vs ETH ~+1.5¢). Thinner market, larger effect. New folder; ready to run.

## Needs data or infrastructure first

- **Ladder relative value** (KXBTC ranges vs the KXBTCD above/below ladder): thin range markets quoted
  around the ladder-implied fair value. Needs recorded hourly-ladder books (`research/ladder_rv.py`).
- **Options-implied vol (Deribit DVOL) as the vol forecast** in a VolFavorite-style model. Needs a DVOL
  history download (public API).
- **Order-book imbalance on spot exchanges.** Needs books recorded live from now (free) or bought
  history (Tardis.dev, Kaiko). Only worth it if the trade-flow idea above shows something.
- **Funding / open interest swings** (OKX public metrics) as a regime filter for momentum vs reversal.

## Tried

- **Fade the previous window's big move at the open** (`strategies/eth-overreact/`): **paper trading**. 15-min
  returns reverse in sign after |z| > 1.5 moves (~56%, all coins, every month); the opening price ignores it. ETH
  walk-forward +2.23¢ (CI +0.37..+4.10, 8/9 months), lockbox pass +2.21¢ (CI −2.1..+6.5). Decaying on ETH (May–Aug ~+0.8¢).
- **ETH overreaction to spot moves / streaks / round-number barriers** (`strategies/eth-overreact/`, H1–H3): rejected at
  research. Kalshi lags spot slightly (< costs); streak count adds nothing beyond the last move's size; round levels
  between spot and strike make the favourite *worse*, not better, and the underdog is still below costs.

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
- **SOL VolFavorite / vol-of-vol (vomma) pricing** (`strategies/sol-vomma/`): rejected at the lockbox. The vomma
  (vol-uncertainty) correction to the binary's price is under 1¢, below a taker's fee plus spread. The eth-volfav method on
  SOL was promising in the walk-forward (+1.93¢, CI +0.57..+3.25, 5/6 months) but lost in the lockbox (−0.89¢; Sep −2.2¢).
- **Settlement-average lock-in / last-minute favourites** (`strategies/settle-lockin/`): rejected at research. The
  market prices the partly fixed 60 s settlement average better than a Binance-based partial-average model at every
  horizon in the final 5 minutes (ETH and SOL); strike-cross cases aren't mispriced; no late favourite-longshot bias.
- **Kalshi trade-size signals** (`strategies/settle-lockin/`, hypothesis 2): rejected at research. Copying or fading
  top-1% Kalshi taker prints loses about fee + spread on ETH and SOL in every size bucket.
- **BTC Kalshi implied vol as the ETH/SOL vol forecast** (`strategies/btc-anchor-vol/`): rejected at research. Adds
  nothing to HAR (out-of-sample R² unchanged), overlaps eth-volfav's signal 93–97%. Spot-distance fair value also
  loses to the market early in the window; no weekend/hour or YES/NO bias positive in both halves.
- **Underdog seller (maker on the favourite-longshot bias)** (`strategies/dog-seller/`): rejected at full test
  (−0.52¢/contract, CI −1.08..+0.08, 1/8 months). Underdog takers do overpay 2–4¢, but back-of-queue maker fills
  are adversely selected (−2.1¢ in 30 s). Needs real queue position to work.
- **US-hours vol seasonality / 9:30 ET opening-bell underdog** (`strategies/us-hours-vol/`): **parked, inconclusive**
  (full 2/3). Crypto vol follows the NY clock (DST test: corr 0.97 NY vs 0.75 UTC); the 9:30 ET window is ~2× the
  9:15 window and Kalshi underprices it (iv ~0.3 log too low). Buying the 10–45¢ underdog in that window on ETH+BTC:
  +4.32¢/ct, CI −1.5..+10.5, 6/9 months, 237 markets. Sample-limited; needs more coins' 15-min markets. Weekend vol,
  the 8:30 release step and the 16:00 step-down are priced correctly (rejected at research).
