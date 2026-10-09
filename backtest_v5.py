"""Backtest v5 — 5 years BTC daily from Bitget (paginated)."""
import warnings; warnings.filterwarnings("ignore")
import requests, pandas as pd, numpy as np, ta
from datetime import datetime, timedelta

BASE = "https://api.bitget.com"


def fetch_all(symbol="BTCUSDT", granularity="1D", target=1900):
    all_rows, seen, end_time = [], set(), None
    for page in range(30):
        params = {"symbol": symbol, "granularity": granularity,
                  "limit": 200, "productType": "USDT-FUTURES"}
        if end_time:
            params["endTime"] = str(end_time)
        r = requests.get(f"{BASE}/api/v2/mix/market/candles", params=params, timeout=15)
        data = r.json()
        if data.get("code") != "00000":
            break
        rows = data.get("data") or []
        if not rows:
            break
        new = 0
        for row in rows:
            ts = int(float(row[0]))
            if ts not in seen:
                seen.add(ts); all_rows.append(row); new += 1
        if new == 0:
            break
        end_time = min(int(float(r[0])) for r in rows) - 1
        if len(all_rows) >= target:
            break
    all_rows.sort(key=lambda r: int(float(r[0])))
    df = pd.DataFrame(all_rows, columns=["ts","open","high","low","close","vol","qv"])
    df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="ms")
    for c in ["open","high","low","close","vol"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[["ts","open","high","low","close","vol"]].set_index("ts").sort_index()


def prep(d):
    d = d.copy()
    d["ema50"] = ta.trend.EMAIndicator(d["close"], 50).ema_indicator()
    d["ema200"] = ta.trend.EMAIndicator(d["close"], 200).ema_indicator()
    d["adx"] = ta.trend.ADXIndicator(d["high"], d["low"], d["close"], 14).adx()
    d["atr"] = ta.volatility.AverageTrueRange(d["high"], d["low"], d["close"], 14).average_true_range()
    return d.dropna(subset=["ema50","ema200","adx","atr"])


def simulate(candle, side, entry, sl, tp):
    h, l = candle["high"], candle["low"]
    if side == "Buy":
        if l <= sl: return "loss", (sl - entry) / entry
        if h >= tp: return "win",  (tp - entry) / entry
    else:
        if h >= sl: return "loss", (entry - sl) / entry
        if l <= tp: return "win",  (entry - tp) / entry
    return "open", 0.0


def run(d, adx_min, rr, label):
    in_pos, entry, sl, tp, ei = False, 0, 0, 0, 0
    trades = []
    for i in range(1, len(d)):
        row, prev = d.iloc[i], d.iloc[i-1]
        if not in_pos:
            golden = prev["ema50"] <= prev["ema200"] and row["ema50"] > row["ema200"]
            if golden and row["adx"] >= adx_min:
                entry = row["close"]
                sl = entry - 2.0 * row["atr"]
                tp = entry + rr * (entry - sl)
                ei = i; in_pos = True
        else:
            hit, exit_price = None, None
            if row["low"] <= sl:  hit, exit_price = "loss", sl
            elif row["high"] >= tp: hit, exit_price = "win",  tp
            else:
                death = prev["ema50"] >= prev["ema200"] and row["ema50"] < row["ema200"]
                if death: hit, exit_price = "exit", row["close"]
            if hit:
                ret = (exit_price - entry) / entry
                trades.append({"result": "win" if ret > 0 else "loss",
                               "return": ret, "bars": i - ei})
                in_pos = False
    if in_pos:
        last = d.iloc[-1]
        ret = (last["close"] - entry) / entry
        trades.append({"result": "win" if ret > 0 else "loss",
                       "return": ret, "bars": len(d) - ei})

    if not trades:
        print(f"  {label}: 0 trades")
        return None
    tdf = pd.DataFrame(trades)
    w = (tdf["result"] == "win").sum()
    l = (tdf["result"] == "loss").sum()
    total = len(tdf)
    avg_w = tdf.loc[tdf["result"]=="win","return"].mean() if w else 0
    avg_l = tdf.loc[tdf["result"]=="loss","return"].mean() if l else 0
    wr = w / total * 100
    fee = 0.002
    eq, curve = 1000.0, [1000.0]
    for r in tdf["return"]:
        eq *= (1 + r - fee); curve.append(eq)
    peak = np.maximum.accumulate(curve)
    dd = ((np.array(curve) - peak) / peak).min() * 100
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    cagr = (eq/1000.0) ** (1/yrs) - 1 if yrs > 0 and eq > 0 else 0
    gp = avg_w * w; gl = abs(avg_l * l)
    pf = gp / gl if gl else float("inf")
    print(f"  {label}: {total}t | WR {wr:.0f}% | PF {pf:.2f} | eq ${eq:.0f} | DD {dd:.1f}% | CAGR {cagr*100:+.1f}%")
    return {"trades": total, "wr": wr, "pf": pf, "eq": eq, "dd": dd, "cagr": cagr}


print("=" * 70)
print("  BACKTEST V5 — BTCUSDT 5 years daily")
print("=" * 70)
raw = fetch_all("BTCUSDT", "1D", 1900)
d = prep(raw)
print(f"  Candles: {len(d)} | {d.index[0].date()} to {d.index[-1].date()}\n")

for adx_min in [20, 22, 24, 26]:
    for rr in [2.0, 2.5, 3.0]:
        run(d, adx_min, rr, f"ADX>={adx_min} RR={rr}")

print("\n" + "=" * 70)
print("  BEST CONFIG: highest PF with >=15 trades")
print("=" * 70)
results = []
for adx_min in [20, 22, 24]:
    for rr in [2.0, 2.5, 3.0]:
        r = run(d, adx_min, rr, f"ADX>={adx_min} RR={rr}")
        if r and r["trades"] >= 15:
            r["label"] = f"ADX>={adx_min} RR={rr}"
            results.append(r)
if results:
    best = max(results, key=lambda x: x["pf"])
    print(f"\n  WINNER: {best['label']}")
    print(f"  Trades: {best['trades']} | WR {best['wr']:.0f}% | PF {best['pf']:.2f} | CAGR {best['cagr']*100:+.1f}% | DD {best['dd']:.1f}%")
else:
    print("  No config meets criteria (15+ trades)")
