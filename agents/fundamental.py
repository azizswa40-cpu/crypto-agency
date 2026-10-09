"""
Fundamental Agent — CoinGecko + Alternative.me (both free, no key).

Signals:
- BTC dominance: rising = risk-off, alts suffer; falling = risk-on
- Fear & Greed trend: extreme readings act as contrarian
"""

import requests


COINGECKO = "https://api.coingecko.com/api/v3"
FEAR_GREED = "https://api.alternative.me/fng/"


class FundamentalAgent:
    def __init__(self):
        pass

    def fetch_btc_dominance(self) -> float:
        try:
            r = requests.get(f"{COINGECKO}/global", timeout=10)
            r.raise_for_status()
            return float(r.json()["data"]["market_cap_percentage"]["btc"])
        except Exception:
            return 0.0

    def fetch_fear_greed_trend(self, days: int = 7) -> list:
        try:
            r = requests.get(FEAR_GREED, params={"limit": days}, timeout=10)
            r.raise_for_status()
            return [int(x["value"]) for x in r.json()["data"]]
        except Exception:
            return []

    def analyze(self) -> dict:
        dominance = self.fetch_btc_dominance()
        fg_trend = self.fetch_fear_greed_trend(7)

        score = 0
        reasons = []

        # BTC dominance
        if dominance > 0:
            if dominance > 58:
                score -= 1
                reasons.append(f"BTC dominance high ({dominance:.1f}%) — risk-off")
            elif dominance < 48:
                score += 1
                reasons.append(f"BTC dominance low ({dominance:.1f}%) — risk-on")
            else:
                reasons.append(f"BTC dominance neutral ({dominance:.1f}%)")

        # Fear & Greed trend — contrarian
        if fg_trend:
            current = fg_trend[0]
            avg_7d = sum(fg_trend) / len(fg_trend)

            if current < 25 and avg_7d < 30:
                score += 1
                reasons.append(f"Fear & Greed deeply fearful ({current}, 7d avg {avg_7d:.0f})")
            elif current > 75 and avg_7d > 70:
                score -= 1
                reasons.append(f"Fear & Greed deeply greedy ({current}, 7d avg {avg_7d:.0f})")
            else:
                reasons.append(f"Fear & Greed normal ({current}, 7d avg {avg_7d:.0f})")

        if score >= 1:
            bias = "BULLISH"
        elif score <= -1:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        return {
            "bias": bias,
            "score": score,
            "btc_dominance": dominance,
            "fear_greed_current": fg_trend[0] if fg_trend else None,
            "fear_greed_avg_7d": sum(fg_trend) / len(fg_trend) if fg_trend else None,
            "reasons": reasons,
        }


if __name__ == "__main__":
    agent = FundamentalAgent()
    result = agent.analyze()

    print("\n=== Fundamental Analysis ===")
    print(f"BTC dominance:        {result['btc_dominance']:.2f}%")
    print(f"Fear & Greed current: {result['fear_greed_current']}")
    print(f"Fear & Greed 7d avg:  {result['fear_greed_avg_7d']:.1f}" if result['fear_greed_avg_7d'] else "Fear & Greed 7d avg:  N/A")
    print(f"\nBias: {result['bias']} (score {result['score']})")
    for r in result["reasons"]:
        print(f"  - {r}")
