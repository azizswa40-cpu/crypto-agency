import ta
from .base import Strategy


class MeanReversionStrategy(Strategy):
    name = "Mean Reversion"
    description = "Buy RSI<30 + lower BB, exit RSI>60."

    def __init__(self, rsi_buy=30, rsi_exit=60):
        self.rsi_buy = rsi_buy
        self.rsi_exit = rsi_exit

    def prepare(self, df):
        d = df.copy()
        d["rsi"] = ta.momentum.RSIIndicator(d["close"], 14).rsi()
        bb = ta.volatility.BollingerBands(d["close"], 20, 2)
        d["bb_lower"] = bb.bollinger_lband()
        d["atr"] = ta.volatility.AverageTrueRange(d["high"], d["low"], d["close"], 14).average_true_range()
        return d

    def generate_signal(self, df, i):
        row = df.iloc[i]
        if any(v != v for v in [row.rsi, row.bb_lower, row.atr]):
            return {"action": "HOLD", "atr": None, "reason": "nan"}
        if row.rsi < self.rsi_buy and row.close < row.bb_lower:
            return {"action": "BUY", "atr": float(row.atr), "reason": "Oversold"}
        if row.rsi > self.rsi_exit:
            return {"action": "EXIT", "atr": float(row.atr), "reason": "RSI exit"}
        return {"action": "HOLD", "atr": float(row.atr), "reason": "no setup"}
