"""
Backtest v3 - Trend-following daily.
Strategy: EMA50/EMA200 cross + ADX filter.
Long-only (crypto trend-following standard).
Tests multiple parameters on 5 years of data.
"""

import warnings
warnings.filterwarnings("ignore")

import requests
import pandas as pd
import numpy as np
import ta
from datetime import datetime, timedelta
from config import BINANCE_API


def fetch_daily(symbol, years=5):
    """Fetch daily candles from Binance public API."""
    url = f"{BINANCE_API}/klines"
    end = int(datetime.utcnow().timestamp() * 1000)
    start = int((datetime.utcnow() - timedelta(days=years * 365)).timestamp() * 1000)
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
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore"])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    for c in ["open", "high", "low", "close", "volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df[["open_time", "open", "high", "low", "close", "volume"]].set_index("open_time")
    return df


def compute(d, fast, slow, adx_len):
    """Compute EMAs and ADX on the full series."""
    d = d.copy()
    d[f"ema_fast"] = ta.trend.EMAIndicator(d["close"], window=fast).ema_indicator()
    d[f"ema_slow"] = ta.trend.EMAIndicator(d["close"], window=slow).ema_indicator()
    d["adx"] = ta.trend.ADXIndicator(d["high"], d["low"], d["close"], window=adx_len).adx()
    d["atr"] = ta.volatility.AverageTrueRange(d["high"], d["low"], d["close"], window=14).average_true_range()
    return d


def simulate_long(entry_price, sl, tp, future_candles):
    """
    Simulate a long trade over subsequent candles.
    Exit on first hit of SL or TP.
    Returns (outcome, exit_price, bars_held).
    """
    for idx, c in enumerate(future_candles):
        if c["low"] <= sl:
            return "loss", sl, idx
        if c["high"] >= tp:
            return "win", tp, idx
    # No hit → exit at last close (time exit)
    last = future_candles[-1]
    return "time", last["close"], len(future_candles) - 1


def run_strategy(d, fast, slow, adx_min, rr, trail_pct, label):
    """
    Long-only: enter when EMA_fast crosses above EMA_slow AND ADX >= adx_min.
    SL = entry - trail_pct * ATR (initial). Actually use fixed: SL = entry - 2*ATR.
    TP = entry + rr * (entry - SL).
    Exit also on EMA death cross.
    """
    d = compute(d, fast, slow, 14)
    d = d.dropna(subset=[f"ema_fast", f"ema_slow", "adx", "atr"])

    if len(d) < 50:
        print(f"  {label}: insufficient data")
        return None

    in_position = False
    trades = []
    entry_price = None
    sl = None
    tp = None
    entry_idx = None

    for i in range(1, len(d)):
        row = d.iloc[i]
        prev = d.iloc[i - 1]

        if not in_position:
            # Golden cross + ADX filter
            golden = prev[f"ema_fast"] <= prev[f"ema_slow"] and row[f"ema_fast"] > row[f"ema_slow"]
            if golden and row["adx"] >= adx_min:
                entry_price = row["close"]
                atr = row["atr"]
                sl = entry_price - 2.0 * atr
                tp = entry_price + rr * (entry_price - sl)
                entry_idx = i
                in_position = True
        else:
            # Check SL/TP hit using current candle
            hit = None
            if row["low"] <= sl:
                hit = "loss"
                exit_price = sl
            elif row["high"] >= tp:
                hit = "win"
                exit_price = tp
            else:
                # Death cross exit
                death = prev[f"ema_fast"] >= prev[f"ema_slow"] and row[f"ema_fast"] < row[f"ema_slow"]
                if death:
                    hit = "exit_signal"
                    exit_price = row["close"]

            if hit:
                ret = (exit_price - entry_price) / entry_price
                trades.append({"result": "win" if ret > 0 else "loss",
                               "return": ret, "bars": i - entry_idx})
                in_position = False

    # Force close last open position
    if in_position:
        last = d.iloc[-1]
        ret = (last["close"] - entry_price) / entry_price
        trades.append({"result": "win" if ret > 0 else "loss",
                       "return": ret, "bars": len(d) - entry_idx})

    return summarize(trades, label, d)


def summarize(trades, label, d):
    if not trades:
        print(f"  {label}: 0 trades")
        return None

    tdf = pd.DataFrame(trades)
    wins = (tdf["result"] == "win").sum()
    losses = (tdf["result"] == "loss").sum()
    total = len(tdf)

    avg_win = tdf.loc[tdf["result"] == "win", "return"].mean() if wins else 0
    avg_loss = tdf.loc[tdf["result"] == "loss", "return"].mean() if losses else 0
    wr = wins / total * 100 if total else 0

    # Equity curve - risk 1% per trade
    risk = 0.01
    eq = 1000.0
    curve = [eq]
    for r in tdf["return"]:
        eq *= (1 + r)
        curve.append(eq)
    peak = np.maximum.accumulate(curve)
    dd = (np.array(curve) - peak) / peak
    max_dd = dd.min() * 100

    # Annualized Sharpe (daily returns from trade distribution)
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    if yrs > 0 and eq > 0:
        cagr = (eq / 1000.0) ** (1 / yrs) - 1
    else:
        cagr = 0

    rets = tdf["return"]
    sharpe = rets.mean() / rets.std() * np.sqrt(252 / max(1, tdf["bars"].mean())) if rets.std() > 0 else 0

    gross_p = avg_win * wins if wins else 0
    gross_l = abs(avg_loss * losses) if losses else 0
    pf = gross_p / gross_l if gross_l else float("inf")

    print(f"  {label}: {total}t | WR {wr:.0f}% | PF {pf:.2f} | "
          f"eq ${eq:.0f} | DD {max_dd:.1f}% | CAGR {cagr*100:+.1f}% | Sharpe {sharpe:.2f}")

    return {"label": label, "trades": total, "wr": wr, "pf": pf,
            "eq": eq, "dd": max_dd, "cagr": cagr, "sharpe": sharpe}


def backtest_symbol(symbol, years=5):
    print(f"\n{'='*70}")
    print(f"  {symbol} - {years} years daily")
    print(f"{'='*70}")
    d = fetch_daily(symbol, years)
    if len(d) < 300:
        print(f"  Insufficient data: {len(d)} candles")
        return
    print(f"  Candles: {len(d)} | {d.index[0].date()} to {d.index[-1].date()}\n")

    print("  FAST/SLOW EMA combinations with ADX filter:")
    results = []
    configs = [
        (20, 50, 20, 2.0, "EMA20/50  ADX>=20 RR=2"),
        (50, 200, 20, 2.0, "EMA50/200 ADX>=20 RR=2"),
        (50, 200, 25, 2.0, "EMA50/200 ADX>=25 RR=2"),
        (50, 200, 25, 3.0, "EMA50/200 ADX>=25 RR=3"),
        (50, 200, 30, 2.0, "EMA50/200 ADX>=30 RR=2"),
        (100, 200, 25, 2.0, "EMA100/200 ADX>=25 RR=2"),
    ]

    for fast, slow, adx_min, rr, label in configs:
        r = run_strategy(d, fast, slow, adx_min, rr, 2.0, label)
        if r:
            results.append(r)

    # Best
    if results:
        best = max(results, key=lambda x: x["pf"])
        print(f"\n  BEST: {best['label']} - PF {best['pf']:.2f}, CAGR {best['cagr']*100:+.1f}%")

    return results


if __name__ == "__main__":
    backtest_symbol("BTCUSDT", 5)
    backtest_symbol("ETHUSDT", 5)
