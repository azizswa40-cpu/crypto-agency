"""
Backtest v4 - Parameter sweep for trend-following.
Finds configs with enough trades to be statistically meaningful.
"""
import warnings
warnings.filterwarnings("ignore")

import requests
import pandas as pd
import numpy as np
import ta
from datetime import datetime, timedelta
from config import BINANCE_API


def fetch_daily(symbol, years=6):
    url = f"{BINANCE_API}/klines"
    end = int(datetime.utcnow().timestamp() * 1000)
    start = int((datetime.utcnow() - timedelta(days=years*365)).timestamp() * 1000)
    all_c = []
    while start < end:
        r = requests.get(url, params={"symbol": symbol, "interval": "1d",
                                       "startTime": start, "limit": 1000}, timeout=15)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        all_c.extend(batch)
        start = batch[-1][0] + 1
    df = pd.DataFrame(all_c, columns=[
        "open_time","open","high","low","close","volume",
        "close_time","quote_volume","trades",
        "taker_buy_base","taker_buy_quote","ignore"])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    for c in ["open","high","low","close","volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    return df[["open_time","open","high","low","close","volume"]].set_index("open_time")


def prep(d):
    d = d.copy()
    d["ema50"] = ta.trend.EMAIndicator(d["close"], 50).ema_indicator()
    d["ema200"] = ta.trend.EMAIndicator(d["close"], 200).ema_indicator()
    d["adx"] = ta.trend.ADXIndicator(d["high"], d["low"], d["close"], 14).adx()
    d["atr"] = ta.volatility.AverageTrueRange(d["high"], d["low"], d["close"], 14).average_true_range()
    return d


def run(d, adx_min, rr, start_date, end_date, label):
    dd = d.loc[start_date:end_date].dropna(subset=["ema50","ema200","adx","atr"]).copy()
    if len(dd) < 100:
        return None

    in_pos = False
    entry = sl = tp = entry_i = None
    trades = []

    for i in range(1, len(dd)):
        row = dd.iloc[i]
        prev = dd.iloc[i-1]

        if not in_pos:
            golden = prev["ema50"] <= prev["ema200"] and row["ema50"] > row["ema200"]
            if golden and row["adx"] >= adx_min:
                entry = row["close"]
                sl = entry - 2.0 * row["atr"]
                tp = entry + rr * (entry - sl)
                entry_i = i
                in_pos = True
        else:
            hit = None
            exit_price = None
            if row["low"] <= sl:
                hit = "loss"; exit_price = sl
            elif row["high"] >= tp:
                hit = "win"; exit_price = tp
            else:
                death = prev["ema50"] >= prev["ema200"] and row["ema50"] < row["ema200"]
                if death:
                    hit = "exit"; exit_price = row["close"]

            if hit:
                ret = (exit_price - entry) / entry
                trades.append({"result": "win" if ret > 0 else "loss",
                               "return": ret, "bars": i - entry_i})
                in_pos = False

    if in_pos:
        last = dd.iloc[-1]
        ret = (last["close"] - entry) / entry
        trades.append({"result": "win" if ret > 0 else "loss",
                       "return": ret, "bars": len(dd) - entry_i})

    if len(trades) < 2:
        return None

    tdf = pd.DataFrame(trades)
    wins = (tdf["result"] == "win").sum()
    losses = (tdf["result"] == "loss").sum()
    total = len(tdf)

    avg_w = tdf.loc[tdf["result"]=="win","return"].mean() if wins else 0
    avg_l = tdf.loc[tdf["result"]=="loss","return"].mean() if losses else 0
    wr = wins / total * 100 if total else 0

    # Fees: 0.1% per side = 0.2% round trip
    fee = 0.002
    eq = 1000.0
    curve = [eq]
    for r in tdf["return"]:
        eq *= (1 + r - fee)
        curve.append(eq)
    peak = np.maximum.accumulate(curve)
    dd_pct = (np.array(curve) - peak) / peak
    max_dd = dd_pct.min() * 100

    yrs = (dd.index[-1] - dd.index[0]).days / 365.25
    cagr = (eq/1000.0) ** (1/yrs) - 1 if yrs > 0 and eq > 0 else 0

    gp = avg_w * wins if wins else 0
    gl = abs(avg_l * losses) if losses else 0
    pf = gp / gl if gl else float("inf")

    print(f"  {label}: {total}t | WR {wr:.0f}% | PF {pf:.2f} | eq ${eq:.0f} | DD {max_dd:.1f}% | CAGR {cagr*100:+.1f}%")
    return {"label": label, "trades": total, "wr": wr, "pf": pf, "eq": eq, "dd": max_dd, "cagr": cagr}


def sweep(symbol):
    print(f"\n{'='*70}")
    print(f"  {symbol} - Parameter Sweep")
    print(f"{'='*70}")

    d = prep(fetch_daily(symbol, years=6))
    print(f"  Data: {len(d)} days ({d.index[0].date()} to {d.index[-1].date()})\n")

    windows = [
        ("5yr (2021-2026)", pd.Timestamp("2021-10-01"), pd.Timestamp("2026-10-08")),
        ("3yr (2023-2026)", pd.Timestamp("2023-10-01"), pd.Timestamp("2026-10-08")),
        ("2yr (2024-2026)", pd.Timestamp("2024-10-01"), pd.Timestamp("2026-10-08")),
    ]

    all_results = []
    for wname, ws, we in windows:
        print(f"  --- {wname} ---")
        for adx_min in [15, 18, 20, 22, 24]:
            for rr in [2.0, 2.5, 3.0]:
                label = f"ADX>={adx_min} RR={rr}"
                r = run(d, adx_min, rr, ws, we, label)
                if r:
                    r["window"] = wname
                    all_results.append(r)
        print()

    if all_results:
        # Filter: at least 15 trades, PF > 1.3, CAGR > 5%
        good = [r for r in all_results if r["trades"] >= 15 and r["pf"] > 1.3 and r["cagr"] > 0.05]
        print(f"  ============================================")
        print(f"  CONFIGS MEETING CRITERIA (15+t, PF>1.3, CAGR>5%):")
        print(f"  ============================================")
        if good:
            for r in sorted(good, key=lambda x: -x["pf"]):
                print(f"    {r['window']} {r['label']}: {r['trades']}t PF {r['pf']:.2f} CAGR {r['cagr']*100:+.1f}%")
        else:
            print("    NONE. No config passed all criteria.")
        print(f"  ============================================\n")


if __name__ == "__main__":
    sweep("BTCUSDT")
    sweep("ETHUSDT")
    sweep("SOLUSDT")
