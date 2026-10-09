"""Market data from Bitget public API v2 with pagination."""
import requests
import pandas as pd
from datetime import datetime, timedelta
from config import CANDLE_LIMIT

BASE = "https://api.bitget.com"


class MarketDataAgent:
    def __init__(self, symbol: str = "BTCUSDT", interval: str = "1D"):
        self.symbol = symbol.upper()
        self.interval = interval

    def _fetch_page(self, end_time_ms=None):
        """Fetch up to 90 candles ending at end_time_ms (or now)."""
        url = f"{BASE}/api/v2/mix/market/candles"
        params = {
            "symbol": self.symbol,
            "granularity": self.interval,
            "limit": 200,
            "productType": "USDT-FUTURES",
        }
        if end_time_ms:
            params["endTime"] = str(end_time_ms)
        try:
            r = requests.get(url, params=params, timeout=15)
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "00000":
                return []
            return data.get("data") or []
        except Exception as e:
            print(f"[MarketData] Page fetch failed: {e}")
            return []

    def fetch_candles(self) -> pd.DataFrame:
        """Paginate backwards to accumulate CANDLE_LIMIT candles."""
        all_rows = []
        seen_ts = set()
        end_time = None
        max_pages = 10

        for page in range(max_pages):
            rows = self._fetch_page(end_time)
            if not rows:
                break

            new_rows = 0
            for row in rows:
                ts_int = int(float(row[0]))
                if ts_int not in seen_ts:
                    seen_ts.add(ts_int)
                    all_rows.append(row)
                    new_rows += 1

            if new_rows == 0:
                break

            # Oldest timestamp in this page becomes the endTime for next request
            oldest_ts = min(int(float(r[0])) for r in rows)
            end_time = oldest_ts - 1

            if len(all_rows) >= CANDLE_LIMIT:
                break

        if not all_rows:
            print(f"[MarketData] No data")
            return pd.DataFrame()

        # Sort ascending and take last CANDLE_LIMIT
        all_rows.sort(key=lambda r: int(float(r[0])))
        all_rows = all_rows[-CANDLE_LIMIT:]

        df = pd.DataFrame(all_rows, columns=["ts","open","high","low","close","vol","quote_vol"])
        df["ts"] = pd.to_datetime(df["ts"].astype(float), unit="ms")
        for c in ["open","high","low","close","vol"]:
            df[c] = pd.to_numeric(df[c], errors="coerce")
        df = df[["ts","open","high","low","close","vol"]].set_index("ts").sort_index()
        df = df[~df.index.duplicated(keep="first")]
        return df

    def get_latest_price(self) -> float:
        try:
            r = requests.get(f"{BASE}/api/v2/mix/market/symbol-price",
                             params={"symbol": self.symbol, "productType": "USDT-FUTURES"},
                             timeout=10)
            r.raise_for_status()
            data = r.json()
            if data.get("code") != "00000":
                return 0.0
            return float(data["data"][0]["price"])
        except Exception as e:
            print(f"[MarketData] Price failed: {e}")
            return 0.0
