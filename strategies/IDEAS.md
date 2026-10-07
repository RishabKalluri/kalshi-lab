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

## Needs data or infrastructure first

- **Ladder relative value** (KXBTC ranges vs the KXBTCD above/below ladder): thin range markets quoted
  around the ladder-implied fair value. Needs recorded hourly-ladder books (`research/ladder_rv.py`).
- **Options-implied vol (Deribit DVOL) as the vol forecast** in a VolFavorite-style model. Needs a DVOL
  history download (public API).
- **Order-book imbalance on spot exchanges.** Needs books recorded live from now (free) or bought
  history (Tardis.dev, Kaiko). Only worth it if the trade-flow idea above shows something.
- **Funding / open interest swings** (OKX public metrics) as a regime filter for momentum vs reversal. (Funding-*time* drift
  screened in `btc-funding`: nothing; a funding-rate *regime filter* still needs OKX funding/OI history.)

## Tried

- **BTC funding-time drift** (`strategies/btc-funding/`): rejected at research. No premium-signed drift or vol bump in BTC
  spot in the 15 minutes before/after 00/08/16 UTC that holds in both halves; OKX perp vs Binance spot is a constant
  ~−4.7 bp venue gap, useless as a funding-sign proxy.
- **BTC late-confirmed reversal (eth-midrev's rule on BTC)** (`strategies/btc-midrev/`, H1): rejected at research.
  +6.2¢ Jan–Apr, −2.3¢ May–Aug: decayed on BTC like the plain reversal.
- **BTC market-wide burst reversal** (`strategies/btc-midrev/`, H2): **parked, inconclusive** (full 1/3). Fade BTC at the
  open only when the BTC/ETH/SOL basket burst into the boundary: +3.50¢/ct, CI −0.56..+7.51, 6/8 months, but Jun −0.6, Jul
  −1.0, 2× latency +1.1¢. BTC-only bursts *stick* (fade −7¢ May–Aug in research); worth checking the basket filter on
  ETH/SOL's rules. Perp-taker-driven bursts reverse *less* (H3, rejected).

- **SOL late-confirmed reversal at the open** (`strategies/sol-midrev/`): **paper trading**. eth-midrev's rule unchanged on
  KXSOL15M: walk-forward +8.77¢ (CI +3.6..+13.7, 7/8 months, +4.2¢ at 2× latency), lockbox pass but weak: +2.11¢
  (CI −7.3..+10.8; Sep −1.0¢). Live-vs-Binance rv ratio SOL 1.11 (paper rv_scale), ETH 1.01 (ETH traders use 1.09).

- **Late-confirmed reversal at the open** (`strategies/eth-midrev/`): **paper trading**. The 15-min reversal lives at
  window boundaries; fading |z15|>1.5 only when the last 5 min also ran |z5|>1.5 the same way: walk-forward +5.42¢
  (CI +2.0..+8.9, 7/9 months, +6.6¢ at 2× latency), lockbox pass +6.89¢ (CI −1.5..+14.8). Subset of eth-overreact's
  trades. Same split holds on SOL (research +7.7/+9.7¢) → worth a SOL folder. Dead in the same folder (research):
  mid-window fade, favourite after in-window moves, BTC→ETH lead-lag, ETH-vs-BTC idiosyncratic reversal, 08:00 UTC expiry.

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
