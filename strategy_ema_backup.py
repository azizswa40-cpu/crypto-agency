"""BTC trend-following strategy — EMA50/200 cross + ADX filter."""
import ta


def compute_indicators(df, ema_fast=50, ema_slow=200):
    d = df.copy()
    d["ema_fast"] = ta.trend.EMAIndicator(d["close"], window=ema_fast).ema_indicator()
    d["ema_slow"] = ta.trend.EMAIndicator(d["close"], window=ema_slow).ema_indicator()
    d["adx"] = ta.trend.ADXIndicator(d["high"], d["low"], d["close"], window=14).adx()
    d["atr"] = ta.volatility.AverageTrueRange(
        d["high"], d["low"], d["close"], window=14
    ).average_true_range()
    return d


def evaluate(df, ema_fast=50, ema_slow=200, adx_min=22):
    if len(df) < 250:
        return None
    d = compute_indicators(df, ema_fast, ema_slow)
    d = d.dropna(subset=["ema_fast", "ema_slow", "adx", "atr"])
    if len(d) < 2:
        return None
    last = d.iloc[-1]
    prev = d.iloc[-2]

    golden = prev["ema_fast"] <= prev["ema_slow"] and last["ema_fast"] > last["ema_slow"]
    death = prev["ema_fast"] >= prev["ema_slow"] and last["ema_fast"] < last["ema_slow"]

    info = {
        "price": float(last["close"]),
        "ema_fast": float(last["ema_fast"]),
        "ema_slow": float(last["ema_slow"]),
        "adx": float(last["adx"]),
        "atr": float(last["atr"]),
        "trend_up": bool(last["ema_fast"] > last["ema_slow"]),
        "golden_cross": bool(golden),
        "death_cross": bool(death),
    }

    if golden and last["adx"] >= adx_min:
        info["signal"] = "BUY"
        info["reason"] = f"Golden cross EMA{ema_fast}/EMA{ema_slow}, ADX {last['adx']:.1f} >= {adx_min}"
    elif death:
        info["signal"] = "EXIT"
        info["reason"] = f"Death cross EMA{ema_fast}/EMA{ema_slow}"
    else:
        info["signal"] = "HOLD"
        info["reason"] = f"EMA trend {'up' if info['trend_up'] else 'down'}, ADX {last['adx']:.1f}"
    return info
