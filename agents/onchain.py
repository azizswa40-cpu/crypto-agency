"""
On-Chain Agent — OKX public API (no key required).

Signals:
- Funding rate: positive = longs paying shorts = crowd is long (bearish contrarian)
- Open interest trend: rising OI + rising price = strong trend
- Long/short account ratio: extreme readings = contrarian signal
"""

import requests


OKX_BASE = "https://www.okx.com/api/v5"


class OnChainAgent:
    def __init__(self, symbol: str = "BTCUSDT"):
        self.symbol = symbol.upper()
        # Map BTCUSDT → BTC-USDT-SWAP
        base = self.symbol.replace("USDT", "")
        self.inst_id = f"{base}-USDT-SWAP"
        self.ccy = base

    def _get(self, path: str, params: dict) -> dict:
        try:
            r = requests.get(f"{OKX_BASE}{path}", params=params, timeout=10)
            r.raise_for_status()
            return r.json()
        except Exception as e:
            return {"error": str(e), "data": []}

    def fetch_funding_rate(self) -> float:
        r = self._get("/public/funding-rate", {"instId": self.inst_id})
        try:
            return float(r["data"][0]["fundingRate"])
        except Exception:
            return 0.0

    def fetch_open_interest(self) -> float:
        r = self._get("/public/open-interest", {"instType": "SWAP", "instId": self.inst_id})
        try:
            return float(r["data"][0]["oi"])
        except Exception:
            return 0.0

    def fetch_long_short_ratio(self) -> float:
        r = self._get(
            "/rubik/stat/contracts/long-short-account-ratio",
            {"ccy": self.ccy, "period": "4H"},
        )
        try:
            return float(r["data"][0][1])
        except Exception:
            return 1.0

    def analyze(self) -> dict:
        funding = self.fetch_funding_rate()
        oi = self.fetch_open_interest()
        ls_ratio = self.fetch_long_short_ratio()

        score = 0
        reasons = []

        # Funding rate contrarian
        # > 0.03% per 8h = crowded long = bearish
        # < -0.01% = crowded short = bullish
        if funding > 0.0003:
            score -= 1
            reasons.append(f"Funding rate high ({funding*100:.4f}%) — crowded longs")
        elif funding < -0.0001:
            score += 1
            reasons.append(f"Funding rate negative ({funding*100:.4f}%) — crowded shorts")
        else:
            reasons.append(f"Funding rate neutral ({funding*100:.4f}%)")

        # Long/short ratio contrarian
        if ls_ratio > 2.0:
            score -= 1
            reasons.append(f"Long/short ratio extreme long ({ls_ratio:.2f})")
        elif ls_ratio < 0.6:
            score += 1
            reasons.append(f"Long/short ratio extreme short ({ls_ratio:.2f})")
        else:
            reasons.append(f"Long/short ratio balanced ({ls_ratio:.2f})")

        if score >= 1:
            bias = "BULLISH"
        elif score <= -1:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        return {
            "bias": bias,
            "score": score,
            "funding_rate": funding,
            "open_interest": oi,
            "long_short_ratio": ls_ratio,
            "reasons": reasons,
        }


if __name__ == "__main__":
    agent = OnChainAgent("BTCUSDT")
    result = agent.analyze()

    print("\n=== On-Chain Analysis: BTCUSDT ===")
    print(f"Funding rate:      {result['funding_rate']*100:.4f}%")
    print(f"Open interest:     {result['open_interest']:.2f}")
    print(f"Long/short ratio:  {result['long_short_ratio']:.2f}")
    print(f"\nBias: {result['bias']} (score {result['score']})")
    for r in result["reasons"]:
        print(f"  - {r}")
