"""
Market Data Agent — OKX public API (free, no key required).
Replaces Binance for candles and prices.
"""
import requests
import pandas as pd
from config import CANDLE_LIMIT

OKX_BASE = "https://www.okx.com/api/v5"


class MarketDataAgent:
    def __init__(self, symbol: str = "BTCUSDT", interval: str = "1D"):
        self.symbol = symbol.upper()
        self.interval = interval
        self.inst_id = self.symbol.replace("USDT", "-USDT-SWAP")

    def fetch_candles(self) -> pd.DataFrame:
        """Fetch OHLCV candles from OKX public API."""
        url = f"{OKX_BASE}/market/candles"
        params = {"instId": self.inst_id, "bar": self.interval, "limit": CANDLE_LIMIT}
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "0":
                print(f"[MarketData] OKX error: {data.get('msg')}")
                return pd.DataFrame()
            raw = data["data"]
        except Exception as e:
            print(f"[MarketData] OKX fetch failed: {e}")
            return pd.DataFrame()

        df = pd.DataFrame(raw, columns=[
            "ts", "open", "high", "low", "close", "vol", "volCcy", "volCcyQuote", "confirm"
        ])
        df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="ms")
        for col in ["open", "high", "low", "close", "vol"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df = df[["ts", "open", "high", "low", "close", "vol"]]
        df.set_index("ts", inplace=True)
        df.sort_index(inplace=True)
        return df

    def get_latest_price(self) -> float:
        url = f"{OKX_BASE}/market/ticker"
        try:
            r = requests.get(url, params={"instId": self.inst_id}, timeout=10)
            r.raise_for_status()
            return float(r.json()["data"][0]["last"])
        except Exception as e:
            print(f"[MarketData] Price fetch failed: {e}")
            return 0.0
