import ta
from .base import Strategy


class MomentumStrategy(Strategy):
    name = "Momentum Breakout"
    description = "Buy on 20d high breakout, exit on 10d low."

    def __init__(self, lookback_high=20, lookback_low=10):
        self.lookback_high = lookback_high
        self.lookback_low = lookback_low

    def prepare(self, df):
        d = df.copy()
        d["high_20"] = d["high"].rolling(self.lookback_high).max()
        d["low_10"] = d["low"].rolling(self.lookback_low).min()
        d["atr"] = ta.volatility.AverageTrueRange(d["high"], d["low"], d["close"], 14).average_true_range()
        return d

    def generate_signal(self, df, i):
        if i < self.lookback_high:
            return {"action": "HOLD", "atr": None, "reason": "warmup"}
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        if any(v != v for v in [row.high_20, row.low_10, row.atr]):
            return {"action": "HOLD", "atr": None, "reason": "nan"}
        if row.close > prev.high_20:
            return {"action": "BUY", "atr": float(row.atr), "reason": "20d breakout"}
        if row.close < row.low_10:
            return {"action": "EXIT", "atr": float(row.atr), "reason": "10d low"}
        return {"action": "HOLD", "atr": float(row.atr), "reason": "no setup"}
