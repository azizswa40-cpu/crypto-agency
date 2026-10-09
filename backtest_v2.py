"""
Backtest v2 - FAST + multi-factor.
Combines Technical Analysis + Fear & Greed historical.
Tests multiple thresholds in one pass.
"""

import warnings
warnings.filterwarnings("ignore")

import requests
import pandas as pd
import numpy as np
import ta
from datetime import datetime, timedelta
from config import BINANCE_API, FEAR_GREED_API


def fetch_candles(symbol, interval="4h", days=365):
    url = f"{BINANCE_API}/klines"
    end = int(datetime.utcnow().timestamp() * 1000)
    start = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)
    all_c = []
    while start < end:
        r = requests.get(url, params={"symbol": symbol, "interval": interval,
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


def fetch_fg_history():
    r = requests.get(FEAR_GREED_API, params={"limit": 0, "format": "json"}, timeout=15)
    r.raise_for_status()
    data = r.json()["data"]
    return {int(d["timestamp"]) // 86400 * 86400: int(d["value"]) for d in data}


def get_fg(fg_dict, ts):
    day = int(ts.timestamp()) // 86400 * 86400
    for delta in [0, -86400, -172800, -259200, -345600]:
        if day + delta in fg_dict:
            return fg_dict[day + delta]
    return 50


def compute_indicators(df):
    d = df.copy()
    d["rsi"] = ta.momentum.RSIIndicator(d["close"], window=14).rsi()
    macd = ta.trend.MACD(d["close"])
    d["macd"] = macd.macd()
    d["macd_signal"] = macd.macd_signal()
    d["ema20"] = ta.trend.EMAIndicator(d["close"], window=20).ema_indicator()
    d["ema50"] = ta.trend.EMAIndicator(d["close"], window=50).ema_indicator()
    bb = ta.volatility.BollingerBands(d["close"], window=20, window_dev=2)
    d["bb_upper"] = bb.bollinger_hband()
    d["bb_lower"] = bb.bollinger_lband()
    d["atr"] = ta.volatility.AverageTrueRange(d["high"], d["low"], d["close"], window=14).average_true_range()
    return d


def ta_score_at(d, i):
    """Compute TA bias score for candle i using pre-computed indicators."""
    row = d.iloc[i]
    prev = d.iloc[i - 1]
    score = 0

    if pd.isna(row["rsi"]) or pd.isna(row["ema50"]):
        return None

    if row["rsi"] < 30:
        score += 1
    elif row["rsi"] > 70:
        score -= 1

    if row["macd"] > row["macd_signal"] and prev["macd"] <= prev["macd_signal"]:
        score += 2
    elif row["macd"] < row["macd_signal"] and prev["macd"] >= prev["macd_signal"]:
        score -= 2

    if row["ema20"] > row["ema50"]:
        score += 1
    else:
        score -= 1

    if row["close"] < row["bb_lower"]:
        score += 1
    elif row["close"] > row["bb_upper"]:
        score -= 1

    return score


def fg_score_at(fg_value):
    """Contrarian Fear & Greed score."""
    if fg_value <= 20:
        return 2
    if fg_value <= 35:
        return 1
    if fg_value >= 80:
        return -2
    if fg_value >= 65:
        return -1
    return 0


def simulate(candle, side, entry, sl, tp):
    high, low = candle["high"], candle["low"]
    if side == "Buy":
        if low <= sl:
            return "loss", (sl - entry) / entry
        if high >= tp:
            return "win", (tp - entry) / entry
    else:
        if high >= sl:
            return "loss", (entry - sl) / entry
        if low <= tp:
            return "win", (entry - tp) / entry
    return "open", 0.0


def run_strategy(df, fg_dict, min_ta, min_composite, use_fg, label):
    d = compute_indicators(df)
    trades = []

    for i in range(60, len(d) - 1):
        ta_s = ta_score_at(d, i)
        if ta_s is None:
            continue

        row = d.iloc[i]
        fg_val = get_fg(fg_dict, d.index[i])
        fgs = fg_score_at(fg_val) if use_fg else 0
        composite = ta_s + fgs

        if use_fg:
            if ta_s < min_ta or composite < min_composite:
                continue
        else:
            if abs(ta_s) < min_ta:
                continue

        entry = row["close"]
        atr = row["atr"]
        if pd.isna(atr) or atr <= 0:
            continue

        if composite > 0 or (not use_fg and ta_s > 0):
            side = "Buy"
            sl = entry - 2.0 * atr
            tp = entry + 3.0 * atr
        else:
            side = "Sell"
            sl = entry + 2.0 * atr
            tp = entry - 3.0 * atr

        outcome, ret = simulate(d.iloc[i + 1], side, entry, sl, tp)
        if outcome != "open":
            trades.append({"result": outcome, "return": ret})

    return summarize(trades, label)


def summarize(trades, label):
    if not trades:
        print(f"  {label}: no trades")
        return None
    tdf = pd.DataFrame(trades)
    wins = (tdf["result"] == "win").sum()
    losses = (tdf["result"] == "loss").sum()
    total = wins + losses
    if total == 0:
        return None

    avg_win = tdf.loc[tdf["result"] == "win", "return"].mean() if wins else 0
    avg_loss = tdf.loc[tdf["result"] == "loss", "return"].mean() if losses else 0
    wr = wins / total * 100

    risk = 0.01
    eq = 1000.0
    curve = [eq]
    for r in tdf["return"]:
        eq *= (1 + r * risk)
        curve.append(eq)
    peak = np.maximum.accumulate(curve)
    dd = (np.array(curve) - peak) / peak
    max_dd = dd.min() * 100

    rets = tdf["return"] * risk
    sharpe = rets.mean() / rets.std() * np.sqrt(365) if rets.std() > 0 else 0
    gross_p = avg_win * wins
    gross_l = abs(avg_loss * losses)
    pf = gross_p / gross_l if gross_l else float("inf")

    print(f"  {label}: {total} trades | WR {wr:.1f}% | PF {pf:.2f} | "
          f"eq ${eq:.0f} | DD {max_dd:.1f}% | Sharpe {sharpe:.2f}")
    return {"trades": total, "wr": wr, "pf": pf, "eq": eq, "dd": max_dd, "sharpe": sharpe}


def backtest_symbol(symbol, days=365):
    print(f"\n{'='*60}")
    print(f"  {symbol} - {days} days, 4h candles")
    print(f"{'='*60}")
    df = fetch_candles(symbol, "4h", days)
    fg = fetch_fg_history()
    print(f"  Candles: {len(df)} | F&G days: {len(fg)}\n")

    print("  OPTION A - TA only, varying thresholds:")
    run_strategy(df, fg, min_ta=2, min_composite=0, use_fg=False, label="  TA >= 2       ")
    run_strategy(df, fg, min_ta=3, min_composite=0, use_fg=False, label="  TA >= 3       ")

    print("\n  OPTION B - TA + Fear&Greed combined:")
    run_strategy(df, fg, min_ta=1, min_composite=2, use_fg=True, label="  TA>=1, comp>=2")
    run_strategy(df, fg, min_ta=2, min_composite=3, use_fg=True, label="  TA>=2, comp>=3")
    run_strategy(df, fg, min_ta=0, min_composite=2, use_fg=True, label="  TA>=0, comp>=2")


if __name__ == "__main__":
    backtest_symbol("BTCUSDT", 365)
    backtest_symbol("ETHUSDT", 365)
