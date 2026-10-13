"""The one place markets are configured. Adding a Kalshi series = one entry in MARKETS:

  live_spot      exchange feeds the recorder streams to track the settlement index ("exchange:symbol";
                 exchanges: coinbase, kraken, bitstamp, okx)
  backfill_spot  public history for backtests: {"binance": "BTCUSDT"} (1s), {"okx": "XAU-USDT-SWAP"} (1m),
                 {"coinbase": "BTC-USD"} (1m)
  flow           order-flow history (taker buy/sell volume per second, data/backfill.py backfill_flow):
                 {"binance": "BTCUSDT"} spot 1s klines, {"okx": "BTC-USDT-SWAP"} perpetual trades. Research
                 only for now: the recorder doesn't stream these live yet. (Binance futures would be the
                 natural perp source, but its API is blocked from US IPs, so live trading couldn't use it.)
  settlement     "avg60": 60s average vs 60s average before open (CF Benchmarks crypto)
                 "point": one 1-minute close vs the close at open (Pyth gold)
  record         whether the recorder captures it by default
  book_depth     contracts at the best price in backfill tests (history has trades but no order books);
                 the 25th percentile of real best-price depth measured from recorded books (Sep 30 2026)

  lookahead_s    subscribe to markets closing within this many seconds (default 1800, for 15-minute series)
  needs_strike   wait for floor_strike on discovery (default True; bracket markets may never have one)
  settle_poll_s  min seconds between settlement checks per closed market (default: every discovery poll)

Backfill of Kalshi trades works for any series without an entry (no spot), e.g. KXBTC / KXBTCD ladders.
"""

MARKETS = {
    "KXBTC15M": dict(live_spot=["coinbase:BTC-USD", "kraken:BTC/USD", "bitstamp:btcusd"],  # BRTI constituents
                     backfill_spot={"binance": "BTCUSDT", "coinbase": "BTC-USD"},
                     flow={"binance": "BTCUSDT", "okx": "BTC-USDT-SWAP"}, settlement="avg60", record=True,
                     book_depth=2088),
    "KXETH15M": dict(live_spot=["coinbase:ETH-USD", "kraken:ETH/USD", "bitstamp:ethusd"],
                     backfill_spot={"binance": "ETHUSDT", "coinbase": "ETH-USD"},
                     flow={"binance": "ETHUSDT", "okx": "ETH-USDT-SWAP"}, settlement="avg60", record=True,
                     book_depth=43),
    # Added Oct 1 2026: about 1/3 of ETH's volume, so likely less efficient. book_depth is provisional:
    # 3 hours of recorded books (8 markets, overnight US) gave p25 = 10 contracts vs 34 for ETH measured the
    # same way (ETH's configured 43 came from a longer sample), so 13. Re-measure after a full day.
    "KXSOL15M": dict(live_spot=["coinbase:SOL-USD", "kraken:SOL/USD", "bitstamp:solusd"],
                     backfill_spot={"binance": "SOLUSDT", "coinbase": "SOL-USD"},
                     flow={"binance": "SOLUSDT", "okx": "SOL-USDT-SWAP"}, settlement="avg60", record=True,
                     book_depth=13),
    # Added Oct 13 2026 for VolFavorite expansion (retail-heavier alts; Kalshi series since Feb 11 / Mar 19).
    # Backfill only for now (record=False): turn on recording once a backtest says they're worth paper.
    # book_depth is a placeholder (SOL's): re-measure from recorded books before trusting capacity numbers.
    "KXXRP15M": dict(live_spot=["coinbase:XRP-USD", "kraken:XRP/USD", "bitstamp:xrpusd"],
                     backfill_spot={"binance": "XRPUSDT", "coinbase": "XRP-USD"},
                     settlement="avg60", record=False, book_depth=13),
    "KXDOGE15M": dict(live_spot=["coinbase:DOGE-USD", "kraken:DOGE/USD", "bitstamp:dogeusd"],
                      backfill_spot={"binance": "DOGEUSDT", "coinbase": "DOGE-USD"},
                      settlement="avg60", record=False, book_depth=13),
    # Gold settles on Pyth (key-gated). OKX's XAU perp tracks it within ~$1 over 15 minutes.
    "KXGOLD15M": dict(live_spot=["okx:XAU-USDT-SWAP"], backfill_spot={"okx": "XAU-USDT-SWAP"},
                      settlement="point", record=True, book_depth=635),
}

# Weather (added Oct 13 2026): books for market-making research. The category survey found takers overpay here
# (cheap brackets), with no maker fees. No spot feed; recorded by a separate unit (kalshi-recorder-weather,
# `kalshi-lab record --series` WEATHER) so the crypto recorder never restarts for it. Markets open ~14:00 UTC the
# day before and close 05:00 UTC the day after; settlement comes hours later from the NWS climate report.
WEATHER = ["KXRAIN", "KXHIGHLAX", "KXHIGHMIA", "KXHIGHNY", "KXHIGHCHI", "KXHIGHAUS", "KXHIGHTDAL", "KXHIGHTPHX",
           "KXHIGHTHOU", "KXHIGHTATL", "KXHIGHTBOS"]
for _s in WEATHER:
    MARKETS[_s] = dict(live_spot=[], settlement="nws", record=False, lookahead_s=3 * 86400, needs_strike=False,
                       settle_poll_s=600)

# Backward-compatible views.
SERIES = {s: m["live_spot"] for s, m in MARKETS.items()}
RECORD_DEFAULT = [s for s, m in MARKETS.items() if m.get("record")]


def stream_name(spec: str) -> str:
    """'coinbase:BTC-USD' -> 'coinbase_btcusd' (the recorder's spot/<name> stream)."""
    exchange, sym = spec.split(":", 1)
    return f"{exchange}_{sym.replace('/', '').replace('-', '').lower()}"


def backfill_stream(exchange: str, symbol: str) -> str:
    """Name of the backfilled spot stream for (exchange, symbol), matching data/backfill.py."""
    base = f"{exchange}_{symbol.replace('-', '').replace('/', '').lower()}"
    return base + ("_1m" if exchange == "okx" else "")


def book_depth(series: str) -> float | None:
    return MARKETS.get(series, {}).get("book_depth")


def settlement(series: str) -> str:
    return MARKETS.get(series, {}).get("settlement", "avg60")


def spot_map(series: list[str], backfill: bool = False) -> dict[str, list[str]]:
    """series -> the spot streams that track its settlement index."""
    if backfill:
        # Prefer the highest-resolution history: binance 1s, then okx 1m, then coinbase 1m.
        out = {}
        for s in series:
            bs = MARKETS.get(s, {}).get("backfill_spot", {})
            pick = next((backfill_stream(ex, bs[ex]) for ex in ("binance", "okx", "coinbase") if ex in bs), None)
            out[s] = [pick] if pick else []
        return out
    return {s: [stream_name(f) for f in SERIES.get(s, [])] for s in series}
