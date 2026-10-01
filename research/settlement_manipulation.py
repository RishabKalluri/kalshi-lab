"""Is anyone pushing spot during the settlement window? Fingerprints of close manipulation, per coin.

    uv run python research/settlement_manipulation.py [KXBTC15M KXETH15M KXSOL15M ...]

Crypto 15-minute markets settle on the 60s average of a CF Benchmarks index before close (and the next
market's strike is the same 60s average). Someone moving spot to win a Kalshi bet would leave traces:
  1. excess volatility: the last minute before each :00/:15/:30/:45 moves more than the other 14 minutes
  2. snap-back: settlement-minute moves reverse in the minutes after the close
  3. both stronger in close calls (spot near the strike at the start of the window), where a push pays
  4. index vs Binance: the official settlement value (expiration_value) drifts away from Binance's own
     60s average more in close calls (a push on the index's constituent exchanges that Binance doesn't follow)
Each settlement-minute number is compared with the same statistic for the other minutes of the cycle.
Development data only (before the lockbox start).
"""

import json
import math
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

import numpy as np

from kalshi_lab.recorder.config import spot_map
from kalshi_lab.recorder.sink import EXT, read_lines
from kalshi_lab.validate import LOCKBOX_START

BF = Path(os.environ.get("KALSHI_DATA_ROOT", "~/kalshi-data/raw")).expanduser().parent / "backfill"
END = int(LOCKBOX_START.replace(tzinfo=timezone.utc).timestamp())
CYCLE = 900


def load_spot(stream):
    secs, px = [], []
    for f in sorted((BF / "spot" / stream).glob(f"*{EXT}")):
        for line in read_lines(f):
            if line.strip():
                d = json.loads(line)
                secs.append(d["t"] // 10**9)
                px.append(d["m"]["price"])
    secs, px = np.array(secs), np.array(px, dtype=float)
    keep = secs < END
    secs, px = secs[keep], px[keep]
    t0 = int(secs[0]) - int(secs[0]) % CYCLE + CYCLE
    arr = np.full(int(secs[-1]) - t0 + 1, np.nan)
    ok = secs >= t0
    arr[secs[ok] - t0] = px[ok]
    filled = np.where(~np.isnan(arr), np.arange(len(arr)), 0)
    np.maximum.accumulate(filled, out=filled)
    gaps = np.isnan(arr)
    return t0, arr[filled], gaps


def settlements(series):
    """{close_ts: (strike, official 60s average)} from the backfill (dev period only)."""
    out = {}
    d = BF / "kalshi" / series
    if not d.exists():
        return out
    for day in sorted(d.iterdir()):
        for f in day.glob(f"*{EXT}"):
            last = None
            for line in read_lines(f):
                if '"settled"' in line:
                    last = json.loads(line)["m"]["market"]
            if not last or not last.get("expiration_value"):
                continue
            ts = int(datetime.fromisoformat(last["close_time"].replace("Z", "+00:00")).timestamp())
            if ts < END and last.get("floor_strike"):
                out[ts] = (float(last["floor_strike"]), float(str(last["expiration_value"]).replace(",", "")))
    return out


def ci(x):
    x = np.asarray(x, float)
    x = x[~np.isnan(x)]
    m, se = x.mean(), x.std(ddof=1) / math.sqrt(len(x))
    return m, m - 1.96 * se, m + 1.96 * se, len(x)


def corr_ci(a, b, n_boot=400, seed=0):
    ok = ~(np.isnan(a) | np.isnan(b))
    a, b = a[ok], b[ok]
    r = np.corrcoef(a, b)[0, 1]
    if not n_boot:
        return r, np.nan, np.nan, len(a)
    rng = np.random.default_rng(seed)
    bs = [np.corrcoef(a[i], b[i])[0, 1] for i in (rng.integers(0, len(a), len(a)) for _ in range(n_boot))]
    return r, *np.percentile(bs, [2.5, 97.5]), len(a)


def analyse(series):
    stream = spot_map([series], backfill=True)[series][0]
    t0, S, gaps = load_spot(stream)
    n_cycles = (len(S) - 2 * CYCLE) // CYCLE
    lr = np.log(S)
    # per cycle c (boundary B = t0 + (c+1)*900), minute m = 0..14 covers [B-900+60m, B-900+60(m+1)); m = 14 is the
    # settlement window. ret[c, m]: log return over that minute; avg[c, m]: 60s mean price minus price at start.
    base = np.arange(n_cycles)[:, None] * CYCLE + np.arange(15)[None, :] * 60
    start, end = base, base + 60
    bad = np.add.reduceat(gaps[: (n_cycles * CYCLE)].astype(int), np.arange(0, n_cycles * CYCLE, CYCLE)) > 30
    ret = (lr[end] - lr[start]) * 1e4  # bp
    ret[bad] = np.nan
    # "after": the 3 minutes following each minute (for m = 14 that's the first 3 minutes of the next market)
    after = (lr[np.minimum(end + 180, len(lr) - 1)] - lr[end]) * 1e4
    after[bad] = np.nan
    vol_1m = np.nanstd(ret, axis=1, keepdims=True)  # each cycle's own 1-minute vol, to normalise
    z = ret / vol_1m

    # close calls: at the start of the settlement window, spot (Binance) vs our own estimate of the strike
    # (Binance's mean over the 60s before the market opened) is within half a 1-minute standard deviation
    open_win = (np.arange(n_cycles) * CYCLE)[:, None] - 60 + np.arange(60)[None, :]
    strike = np.where(open_win >= 0, S[np.clip(open_win, 0, None)], np.nan).mean(axis=1)
    gap_bp = (lr[start[:, 14]] - np.log(strike)) * 1e4
    close = np.abs(gap_bp) < 0.5 * vol_1m[:, 0]

    days = n_cycles * CYCLE / 86400
    print(f"\n=== {series}  (spot {stream}, {days:.0f} days, {n_cycles:,} cycles, {close.mean():.0%} close calls)")

    print("1. volatility by minute of the 15-min cycle (|return| / that cycle's typical minute; 1.00 = average)")
    rel = np.abs(z)
    rel = rel / np.nanmean(rel)
    row = "   minute " + " ".join(f"{m:>4}" for m in range(15))
    print(row)
    print("   all    " + " ".join(f"{np.nanmean(rel[:, m]):4.2f}" for m in range(15)))
    print("   close  " + " ".join(f"{np.nanmean(rel[close, m]):4.2f}" for m in range(15)))
    s, o = rel[:, 14], rel[:, :14].ravel()
    m1, lo1, hi1, _ = ci(s)
    print(f"   settlement minute: {m1:.3f} (95% CI {lo1:.3f}-{hi1:.3f}) vs other minutes {np.nanmean(o):.3f}")

    print("2. snap-back: correlation of each minute's move with the next 3 minutes (negative = reversal)")
    for label, mask in (("all", np.ones(n_cycles, bool)), ("close calls", close)):
        r, lo, hi, n = corr_ci(ret[mask, 14], after[mask, 14])
        others = [corr_ci(ret[mask, m], after[mask, m], n_boot=0)[0] for m in range(14)]
        print(f"   {label:<12} settlement {r:+.3f} (95% CI {lo:+.3f} to {hi:+.3f}, n={n:,})"
              f" | other minutes median {np.median(others):+.3f} [{min(others):+.3f} to {max(others):+.3f}]")

    # big settlement-minute moves: a push should be big *and* revert. Share of 3-sigma settlement moves
    # that give back >50% within 3 minutes, vs the same for 3-sigma moves in other minutes.
    def giveback(m_idx, mask):
        zz, rr, aa = z[mask][:, m_idx].ravel(), ret[mask][:, m_idx].ravel(), after[mask][:, m_idx].ravel()
        big = np.abs(zz) > 3
        return np.nanmean((-aa[big] / rr[big]) > 0.5), int(big.sum())
    rows_gb = [giveback([m], np.ones(n_cycles, bool)) for m in range(15)]
    print("   3-sigma moves that give back >half in the next 3 min, by minute:")
    print("   minute " + " ".join(f"{m:>4}" for m in range(15)))
    print("   share  " + " ".join(f"{g:4.0%}" for g, _ in rows_gb))
    print("   n      " + " ".join(f"{n:>4}" for _, n in rows_gb))
    # do big settlement-minute moves push spot across the strike (flip the likely winner) more than chance?
    big = np.abs(z[:, 14]) > 2
    toward = np.sign(ret[:, 14]) == -np.sign(gap_bp)
    crosses = toward & (np.abs(ret[:, 14]) > np.abs(gap_bp))
    print(f"   2-sigma settlement moves heading toward the strike: {np.nanmean(toward[big]):.0%} (50% = chance, n={big.sum()}),"
          f" crossing it: {np.nanmean(crosses[big]):.0%}; in close calls toward {np.nanmean(toward[big & close]):.0%} (n={(big & close).sum()})")

    sett = settlements(series)
    if sett:
        bt = t0 + (np.arange(n_cycles) + 1) * CYCLE
        idx = {int(b): c for c, b in enumerate(bt)}
        win = np.arange(-60, 0)
        rows = []
        for ts, (k, official) in sett.items():
            c = idx.get(ts)
            if c is None or bad[c]:
                continue
            ours = S[ts - t0 + win].mean()
            rows.append((c, (official / ours - 1) * 1e4, (k / strike[c] - 1) * 1e4 if not np.isnan(strike[c]) else np.nan))
        rows = np.array(rows)
        c_idx, basis, kbasis = rows[:, 0].astype(int), rows[:, 1], rows[:, 2]
        # remove the slow-moving index-vs-Binance basis (USD vs USDT etc.): compare with the same gap at the strike
        resid = basis - kbasis
        cc = close[c_idx]
        print("4. official index average vs Binance's 60s average at settlement (bp, net of the same gap at the strike)")
        for label, msk in (("close calls", cc), ("others", ~cc)):
            x = resid[msk & ~np.isnan(resid)]
            print(f"   {label:<12} median |gap| {np.median(np.abs(x)):.2f} bp, p95 {np.percentile(np.abs(x), 95):.2f} bp,"
                  f" |gap| > 3 bp in {np.mean(np.abs(x) > 3):.1%} of {len(x):,} markets")
        print(f"   ({len(rows):,} settled markets matched)")


if __name__ == "__main__":
    for s in sys.argv[1:] or ["KXBTC15M", "KXETH15M", "KXSOL15M"]:
        analyse(s)
