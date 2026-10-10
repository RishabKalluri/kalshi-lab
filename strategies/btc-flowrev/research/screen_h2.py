"""H2 screen: does the NY-session return predict the 15:00-16:00 ET windows (ETF fixing hour)? Dev only.
    uv run python strategies/btc-flowrev/research/screen_h2.py"""
import sys
from pathlib import Path
import numpy as np, pandas as pd

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "strategies/eth-overreact/research"))
from panel import load_spot  # noqa: E402

MAY = int(pd.Timestamp("2026-05-01", tz="UTC").timestamp())
HOL = {"2025-12-25", "2026-01-01", "2026-01-19", "2026-02-16", "2026-04-03", "2026-05-25", "2026-06-19", "2026-07-03"}
fee = lambda p: 0.07 * p * (1 - p)
T0, s = load_spot("binance_btcusdt")
cs = np.concatenate([[0.0], np.cumsum(s)])
ls = np.log(s)
c2 = np.concatenate([[0.0], np.cumsum(np.concatenate([[0.0], np.diff(ls) ** 2]))])
avg = lambda j: (cs[j] - cs[j - 60]) / 60

opens = np.arange(((T0 + 90000) // 900 + 1) * 900, T0 + len(s) - 960, 900)
i = opens - T0
w = pd.DataFrame({"open": opens})
w["up"] = (avg(i + 900) >= avg(i)).astype(int)
w["ret"] = np.log(avg(i + 900) / avg(i))
ny = pd.to_datetime(w.open, unit="s", utc=True).dt.tz_convert("America/New_York")
w["slot"] = ny.dt.strftime("%H:%M")
w["date"] = ny.dt.strftime("%Y-%m-%d")
w["wd"] = ny.dt.weekday
w["trading"] = (w.wd < 5) & ~w.date.isin(HOL)
# session open 09:30 ET of the same NY date
sess = (ny.dt.normalize() + pd.Timedelta(hours=9, minutes=30)).map(lambda x: int(x.timestamp())).to_numpy()
el = opens - sess
j = sess - T0
rv = np.sqrt((c2[i] - c2[i - 3600]) / 3600)
w["el"] = el
w["R"] = np.where(el >= 1800, np.log(s[i] / s[j]) / (rv * np.sqrt(np.maximum(el, 1))), np.nan)
w["R24"] = np.log(s[i] / s[i - 86400]) / (rv * np.sqrt(86400))
w["half"] = np.where(w.open < MAY, "A", "B")
w = w.dropna(subset=["R"])
w["sret"] = w.ret / (rv[np.searchsorted(opens, w.open)] * 30)  # standardized window return
etf = w.slot.isin(["15:00", "15:15", "15:30", "15:45"])
print("corr(R, window return z), by group and half")
for lab, m in [("ETF hour, trading days", etf & w.trading), ("ETF hour, weekends/holidays", etf & ~w.trading),
               ("other slots >=10:00, trading days", ~etf & w.trading & (w.el >= 1800) & (w.slot < "17:00")),
               ("17:00-23:45 ET trading days", w.trading & (w.slot >= "17:00"))]:
    g = w[m].groupby("half").apply(lambda x: pd.Series({"corr": x.R.corr(x.sret), "hit": (np.sign(x.R) == np.sign(x.ret)).mean(), "n": len(x)}))
    print(f"  {lab:38s}", g.round(3).to_dict("index"))
print("\nETF-hour, trading days, per slot:")
print(w[etf & w.trading].groupby(["slot", "half"]).apply(lambda x: round(x.R.corr(x.sret), 3)).unstack())
# per-slot corr across the whole trading day (descriptive)
print("\nall trading-day slots corr(R, z) A/B:")
t = w[w.trading & (w.slot >= "10:00") & (w.slot < "17:00")].groupby(["slot", "half"]).apply(lambda x: round(x.R.corr(x.sret), 3)).unstack()
print(t.T.to_string())

# Kalshi: follow the session return at the open in the ETF hour, at next real fills
p = pd.read_parquet(ROOT / "research/data/eth-overreact/KXBTC15M_panel.parquet")
p["open"] = p.close - 900
p = p.merge(w[["open", "R", "slot", "trading", "half"]], on="open")
p["mid"] = (p.ask + p.bid) / 2
for lab, m in [("ETF hour trading days", p.slot.isin(["15:00", "15:15", "15:30", "15:45"]) & p.trading),
               ("ETF hour, |R|>1", p.slot.isin(["15:00", "15:15", "15:30", "15:45"]) & p.trading & (p.R.abs() > 1)),
               ("control: other trading-day slots |R|>1", ~p.slot.isin(["15:00", "15:15", "15:30", "15:45"]) & p.trading & (p.R.abs() > 1))]:
    e = p[m].copy()
    up = e.R > 0
    e["pnl"] = np.where(up, e.y - e.next_ask - fee(e.next_ask), e.next_bid - e.y - fee(e.next_bid))
    e = e.dropna(subset=["pnl"]).sort_values("h", ascending=False).groupby("ticker").head(1)
    g = e.groupby("half").pnl.agg(c=lambda x: 100 * x.mean(), se=lambda x: 100 * x.std() / np.sqrt(len(x)), n="size")
    print(f"follow at open: {lab:40s}", g.round(2).to_dict("index"))

# ---- H3 checks: 16:00 ET slot ----
print("\n== H3: 16:00 ET slot")
for lab, m in [("trading days", (w.slot == "16:00") & w.trading), ("weekends/holidays", (w.slot == "16:00") & ~w.trading),
               ("trading days 16:15", (w.slot == "16:15") & w.trading)]:
    x = w[m]
    g = x.groupby("half").apply(lambda x: pd.Series({"corr": x.R.corr(x.sret), "hit_rev(|R|>1)": (np.sign(x.R) != np.sign(x.ret))[x.R.abs() > 1].mean(), "n": len(x)}))
    print(f"  {lab:20s}", g.round(3).to_dict("index"))
ws = w[(w.slot == "16:00") & w.trading]
print("  monthly corr:", ws.groupby(pd.to_datetime(ws.open, unit="s").dt.strftime("%m")).apply(lambda x: round(x.R.corr(x.sret), 2)).to_dict())
q = p[(p.slot == "16:00") & p.trading & p.mid.between(0.3, 0.7)].copy()
for thr in (0.0, 0.5, 1.0):
    for hh in (870, 840, 810, 780):
        e = q[(q.R.abs() > thr) & (q.h == hh)].copy()
        up = e.R < 0
        e["pnl"] = np.where(up, e.y - e.next_ask - fee(e.next_ask), e.next_bid - e.y - fee(e.next_bid))
        e = e.dropna(subset=["pnl"])
        g = e.groupby("half").pnl.agg(c=lambda x: 100 * x.mean(), se=lambda x: 100 * x.std() / np.sqrt(len(x)), n="size")
        print(f"  fade |R|>{thr} h={hh}:", g.round(2).to_dict("index"))
