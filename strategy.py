"""
Active strategy wrapper — uses Momentum Breakout (best performer in arena v3).

Arena results (avg 3 symbols, 2.5y):
  Momentum Breakout:  +83.8% return,  PF 1.24
  EMA50/200+ADX:       +8.4% return,  PF 0.52
  Buy & Hold:          +6.4% return
  Mean Reversion:     -30.3% return

Momentum logic: BUY on close > 20-day high, EXIT on close < 10-day low.
"""
import ta


def compute_indicators(df, ema_fast=50, ema_slow=200):
    """Kept for backward compatibility with old code paths."""
    d = df.copy()
    d["ema_fast"] = ta.trend.EMAIndicator(d["close"], window=ema_fast).ema_indicator()
    d["ema_slow"] = ta.trend.EMAIndicator(d["close"], window=ema_slow).ema_indicator()
    d["adx"] = ta.trend.ADXIndicator(d["high"], d["low"], d["close"], window=14).adx()
    d["atr"] = ta.volatility.AverageTrueRange(d["high"], d["low"], d["close"], window=14).average_true_range()
    d["high_20"] = d["high"].rolling(20).max()
    d["low_10"] = d["low"].rolling(10).min()
    return d


def evaluate(df, ema_fast=50, ema_slow=200, adx_min=22):
    """
    Momentum Breakout evaluation.
    Returns same dict shape as before, so main.py works unchanged.
    """
    if len(df) < 30:
        return None

    d = compute_indicators(df, ema_fast, ema_slow)
    d = d.dropna(subset=["atr", "high_20", "low_10", "ema_fast", "ema_slow", "adx"])
    if len(d) < 2:
        return None

    last = d.iloc[-1]
    prev = d.iloc[-2]

    price = float(last["close"])
    atr = float(last["atr"])
    high_20 = float(prev["high_20"])
    low_10 = float(last["low_10"])
    trend_up = bool(last["ema_fast"] > last["ema_slow"])

    signal = "HOLD"
    reason = ""

    # Momentum breakout: current close above previous 20-day high
    if price > high_20:
        signal = "BUY"
        reason = f"Breakout above 20d high ${high_20:,.2f}"
    elif price < low_10:
        signal = "EXIT"
        reason = f"Breakdown below 10d low ${low_10:,.2f}"
    else:
        reason = f"Range: 20d high ${high_20:,.2f}, 10d low ${low_10:,.2f}"

    return {
        "price": price,
        "ema_fast": float(last["ema_fast"]),
        "ema_slow": float(last["ema_slow"]),
        "adx": float(last["adx"]),
        "atr": atr,
        "trend_up": trend_up,
        "golden_cross": False,
        "death_cross": False,
        "signal": signal,
        "reason": reason,
        "high_20": high_20,
        "low_10": low_10,
    }
