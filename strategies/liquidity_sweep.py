"""Liquidity sweep — wick pierces swing low/high then closes back."""
import ta
from .base import Strategy


class LiquiditySweepStrategy(Strategy):
    name = "Liquidity Sweep"
    description = "Buy after wick sweeps prior swing low and reclaims it."

    def __init__(self, lookback=20):
        self.lookback = lookback

    def prepare(self, df):
        d = df.copy()
        d["swing_low"] = d["low"].rolling(self.lookback).min()
        d["swing_high"] = d["high"].rolling(self.lookback).max()
        d["atr"] = ta.volatility.AverageTrueRange(
            d["high"], d["low"], d["close"], 14
        ).average_true_range()
        return d

    def generate_signal(self, df, i):
        if i < self.lookback + 1:
            return {"action": "HOLD", "atr": None, "reason": "warmup"}
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        if row.atr != row.atr or row.swing_low != row.swing_low:
            return {"action": "HOLD", "atr": None, "reason": "nan"}
        swept_low = row.low < prev.swing_low and row.close > prev.swing_low
        swept_high = row.high > prev.swing_high and row.close < prev.swing_high
        if swept_low:
            return {"action": "BUY", "atr": float(row.atr),
                    "reason": f"Swept low {prev.swing_low:.0f}"}
        if swept_high:
            return {"action": "EXIT", "atr": float(row.atr),
                    "reason": f"Swept high {prev.swing_high:.0f}"}
        return {"action": "HOLD", "atr": float(row.atr), "reason": "no sweep"}
