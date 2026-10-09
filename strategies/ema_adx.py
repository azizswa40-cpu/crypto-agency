import ta
from .base import Strategy


class EmaAdxStrategy(Strategy):
    name = "EMA50/200 + ADX"
    description = "Trend-following: golden cross EMA50/200 confirmed by ADX >= 22."

    def __init__(self, adx_min=22, rr=3.0):
        self.adx_min = adx_min
        self.rr = rr

    def prepare(self, df):
        d = df.copy()
        d["ema_fast"] = ta.trend.EMAIndicator(d["close"], 50).ema_indicator()
        d["ema_slow"] = ta.trend.EMAIndicator(d["close"], 200).ema_indicator()
        d["adx"] = ta.trend.ADXIndicator(d["high"], d["low"], d["close"], 14).adx()
        d["atr"] = ta.volatility.AverageTrueRange(d["high"], d["low"], d["close"], 14).average_true_range()
        return d

    def generate_signal(self, df, i):
        if i < 1:
            return {"action": "HOLD", "atr": None, "reason": "warmup"}
        row = df.iloc[i]
        prev = df.iloc[i - 1]
        if any(v != v for v in [row.ema_fast, row.ema_slow, row.adx, row.atr]):
            return {"action": "HOLD", "atr": None, "reason": "nan"}
        golden = prev.ema_fast <= prev.ema_slow and row.ema_fast > row.ema_slow
        death = prev.ema_fast >= prev.ema_slow and row.ema_fast < row.ema_slow
        if golden and row.adx >= self.adx_min:
            return {"action": "BUY", "atr": float(row.atr), "reason": "Golden cross"}
        if death:
            return {"action": "EXIT", "atr": float(row.atr), "reason": "Death cross"}
        return {"action": "HOLD", "atr": float(row.atr), "reason": "no setup"}
