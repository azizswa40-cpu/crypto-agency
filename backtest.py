"""
Backtester - validates strategy on historical data.
Uses numeric rules (not the LLM CEO) for speed.
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
from config import BINANCE_API
from agents.technical_analysis import TechnicalAnalysisAgent


def fetch_history(symbol, interval="4h", days=365):
    url = f"{BINANCE_API}/klines"
    end = int(datetime.utcnow().timestamp() * 1000)
    start = int((datetime.utcnow() - timedelta(days=days)).timestamp() * 1000)
    all_candles = []
    while start < end:
        params = {"symbol": symbol, "interval": interval,
                  "startTime": start, "limit": 1000}
        r = requests.get(url, params=params, timeout=15)
        r.raise_for_status()
        batch = r.json()
        if not batch:
            break
        all_candles.extend(batch)
        start = batch[-1][0] + 1
    df = pd.DataFrame(all_candles, columns=[
        "open_time", "open", "high", "low", "close", "volume",
        "close_time", "quote_volume", "trades",
        "taker_buy_base", "taker_buy_quote", "ignore",
    ])
    df["open_time"] = pd.to_datetime(df["open_time"], unit="ms")
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df = df[["open_time", "open", "high", "low", "close", "volume"]]
    df.set_index("open_time", inplace=True)
    return df


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


def run_backtest(symbol="BTCUSDT", interval="4h", days=365):
    print(f"\n[Backtest] {symbol} {interval} - {days} days")
    df = fetch_history(symbol, interval, days)
    print(f"[Backtest] {len(df)} candles loaded")

    trades = []
    for i in range(60, len(df) - 1):
        window = df.iloc[:i + 1].copy()
        try:
            ta = TechnicalAnalysisAgent(window).analyze()
        except Exception:
            continue

        score = ta["bias_score"]
        if score >= 3:
            decision = "BUY"
        elif score <= -3:
            decision = "SELL"
        else:
            continue

        entry = ta["price"]
        atr = ta["atr"]
        if decision == "BUY":
            sl, tp, side = entry - 2.0 * atr, entry + 3.0 * atr, "Buy"
        else:
            sl, tp, side = entry + 2.0 * atr, entry - 3.0 * atr, "Sell"

        outcome, ret = simulate(df.iloc[i + 1], side, entry, sl, tp)
        if outcome != "open":
            trades.append({"time": df.index[i], "side": side,
                           "result": outcome, "return": ret})

    if not trades:
        print("[Backtest] No trades generated.")
        return

    tdf = pd.DataFrame(trades)
    wins = (tdf["result"] == "win").sum()
    losses = (tdf["result"] == "loss").sum()
    total = wins + losses

    avg_win = tdf.loc[tdf["result"] == "win", "return"].mean() if wins else 0
    avg_loss = tdf.loc[tdf["result"] == "loss", "return"].mean() if losses else 0
    win_rate = wins / total * 100 if total else 0

    risk_pct = 0.01
    equity = 1000.0
    curve = [equity]
    for r in tdf["return"]:
        equity *= (1 + r * risk_pct / 0.01 * 0.01)
        curve.append(equity)
    peak = np.maximum.accumulate(curve)
    dd = (np.array(curve) - peak) / peak
    max_dd = dd.min() * 100

    returns_series = tdf["return"] * risk_pct
    sharpe = (returns_series.mean() / returns_series.std() * np.sqrt(252)
              if returns_series.std() > 0 else 0)
    gross_profit = avg_win * wins
    gross_loss = abs(avg_loss * losses)
    pf = gross_profit / gross_loss if gross_loss else float("inf")

    print("\n" + "=" * 60)
    print(f"  BACKTEST RESULTS - {symbol} ({interval}, {days}d)")
    print("=" * 60)
    print(f"  Total trades:      {total}")
    print(f"  Wins / Losses:     {wins} / {losses}")
    print(f"  Win rate:          {win_rate:.1f}%")
    print(f"  Avg win:           {avg_win*100:.2f}%")
    print(f"  Avg loss:          {avg_loss*100:.2f}%")
    print(f"  Profit factor:     {pf:.2f}")
    print(f"  Final equity:      ${equity:.2f} (from $1000)")
    print(f"  Max drawdown:      {max_dd:.2f}%")
    print(f"  Sharpe (ann.):     {sharpe:.2f}")
    print("=" * 60 + "\n")

    tdf.to_csv(f"logs/backtest_{symbol}_{interval}.csv", index=False)
    print(f"[Backtest] Log saved to logs/backtest_{symbol}_{interval}.csv")


if __name__ == "__main__":
    run_backtest("BTCUSDT", "4h", 365)
    run_backtest("ETHUSDT", "4h", 365)
