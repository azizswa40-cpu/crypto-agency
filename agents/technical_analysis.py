"""
Technical Analysis Agent
Computes RSI, MACD, EMA, Bollinger Bands, ATR from candle data.
Produces a directional bias: BULLISH / BEARISH / NEUTRAL.
"""

import pandas as pd
import ta


class TechnicalAnalysisAgent:
    def __init__(self, df: pd.DataFrame):
        if df.empty:
            raise ValueError("Empty dataframe passed to TA agent")
        self.df = df.copy()
        self._compute_indicators()

    def _compute_indicators(self):
        d = self.df

        # RSI (14)
        d["rsi"] = ta.momentum.RSIIndicator(d["close"], window=14).rsi()

        # MACD
        macd = ta.trend.MACD(d["close"])
        d["macd"] = macd.macd()
        d["macd_signal"] = macd.macd_signal()
        d["macd_diff"] = macd.macd_diff()

        # EMA 20 and 50
        d["ema20"] = ta.trend.EMAIndicator(d["close"], window=20).ema_indicator()
        d["ema50"] = ta.trend.EMAIndicator(d["close"], window=50).ema_indicator()

        # Bollinger Bands
        bb = ta.volatility.BollingerBands(d["close"], window=20, window_dev=2)
        d["bb_upper"] = bb.bollinger_hband()
        d["bb_lower"] = bb.bollinger_lband()
        d["bb_mid"] = bb.bollinger_mavg()

        # ATR for stop-loss sizing
        d["atr"] = ta.volatility.AverageTrueRange(
            d["high"], d["low"], d["close"], window=14
        ).average_true_range()

        self.df = d

    def analyze(self) -> dict:
        """Return the latest indicator values + a directional bias."""
        latest = self.df.iloc[-1]
        prev = self.df.iloc[-2]

        bias_score = 0
        reasons = []

        # Rule 1: RSI
        if latest["rsi"] < 30:
            bias_score += 1
            reasons.append(f"RSI oversold ({latest['rsi']:.1f})")
        elif latest["rsi"] > 70:
            bias_score -= 1
            reasons.append(f"RSI overbought ({latest['rsi']:.1f})")

        # Rule 2: MACD cross
        if latest["macd"] > latest["macd_signal"] and prev["macd"] <= prev["macd_signal"]:
            bias_score += 2
            reasons.append("MACD bullish cross")
        elif latest["macd"] < latest["macd_signal"] and prev["macd"] >= prev["macd_signal"]:
            bias_score -= 2
            reasons.append("MACD bearish cross")

        # Rule 3: EMA trend
        if latest["ema20"] > latest["ema50"]:
            bias_score += 1
            reasons.append("EMA20 above EMA50 (uptrend)")
        else:
            bias_score -= 1
            reasons.append("EMA20 below EMA50 (downtrend)")

        # Rule 4: Price vs Bollinger
        if latest["close"] < latest["bb_lower"]:
            bias_score += 1
            reasons.append("Price below lower Bollinger Band")
        elif latest["close"] > latest["bb_upper"]:
            bias_score -= 1
            reasons.append("Price above upper Bollinger Band")

        if bias_score >= 2:
            bias = "BULLISH"
        elif bias_score <= -2:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        return {
            "price": float(latest["close"]),
            "rsi": float(latest["rsi"]),
            "macd": float(latest["macd"]),
            "macd_signal": float(latest["macd_signal"]),
            "ema20": float(latest["ema20"]),
            "ema50": float(latest["ema50"]),
            "bb_upper": float(latest["bb_upper"]),
            "bb_lower": float(latest["bb_lower"]),
            "atr": float(latest["atr"]),
            "bias": bias,
            "bias_score": bias_score,
            "reasons": reasons,
        }


if __name__ == "__main__":
    from agents.market_data import MarketDataAgent

    md = MarketDataAgent("BTCUSDT")
    df = md.fetch_candles()
    ta_agent = TechnicalAnalysisAgent(df)
    result = ta_agent.analyze()

    print("\n=== Technical Analysis: BTCUSDT ===")
    print(f"Price:        ${result['price']:,.2f}")
    print(f"RSI:          {result['rsi']:.2f}")
    print(f"MACD:         {result['macd']:.2f} (signal {result['macd_signal']:.2f})")
    print(f"EMA20/EMA50:  {result['ema20']:.2f} / {result['ema50']:.2f}")
    print(f"ATR:          {result['atr']:.2f}")
    print(f"\nBias:         {result['bias']} (score {result['bias_score']})")
    print("Reasons:")
    for r in result["reasons"]:
        print(f"  - {r}")

