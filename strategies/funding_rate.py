"""Funding Rate contrarian — independent data source (Bitget API)."""
import requests
from .base import Strategy


class FundingRateStrategy(Strategy):
    name = "Funding Rate"
    description = "Contrarian on extreme funding rates."

    BASE = "https://api.bitget.com"

    def __init__(self, high=0.0005, low=-0.0001):
        self.high = high
        self.low = low
        self._cache = {}

    def prepare(self, df):
        import ta
        d = df.copy()
        d["atr"] = ta.volatility.AverageTrueRange(
            d["high"], d["low"], d["close"], 14
        ).average_true_range()
        return d

    def _fetch(self, symbol="BTCUSDT"):
        if symbol in self._cache:
            return self._cache[symbol]
        try:
            r = requests.get(
                f"{self.BASE}/api/v2/mix/market/current-fund-rate",
                params={"symbol": symbol, "productType": "USDT-FUTURES"},
                timeout=10,
            )
            data = r.json()
            if data.get("code") == "00000" and data.get("data"):
                rate = float(data["data"][0].get("fundingRate", 0))
                self._cache[symbol] = rate
                return rate
        except Exception:
            pass
        self._cache[symbol] = 0.0
        return 0.0

    def generate_signal(self, df, i):
        if i != len(df) - 1:
            return {"action": "HOLD", "atr": None, "reason": "not last"}
        atr = df.iloc[i].get("atr")
        if atr is None or atr != atr or atr <= 0:
            return {"action": "HOLD", "atr": None, "reason": "no atr"}
        rate = self._fetch()
        if rate >= self.high:
            return {"action": "EXIT", "atr": float(atr),
                    "reason": f"Funding {rate*100:.4f}% high"}
        if rate <= self.low:
            return {"action": "BUY", "atr": float(atr),
                    "reason": f"Funding {rate*100:.4f}% neg"}
        return {"action": "HOLD", "atr": float(atr),
                "reason": f"Funding {rate*100:.4f}% neutral"}
