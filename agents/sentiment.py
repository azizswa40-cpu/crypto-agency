from config import CRYPTOCOMPARE_API_KEY
"""
Sentiment Agent
Fetches:
  1. Crypto Fear & Greed Index (Alternative.me) — free, unlimited, no key
  2. Latest crypto news headlines (CryptoCompare) — free, 100k req/month, no key

Produces a sentiment score: BULLISH / BEARISH / NEUTRAL
"""

import requests
from config import FEAR_GREED_API, CRYPTOCOMPARE_API


class SentimentAgent:
    def __init__(self):
        pass

    # ------------------------------------------------------------------
    # 1. Fear & Greed Index
    # ------------------------------------------------------------------
    def fetch_fear_greed(self) -> dict:
        """
        Fetch the current Crypto Fear & Greed Index.
        Returns dict with value (0-100), classification, and timestamp.
        """
        try:
            r = requests.get(FEAR_GREED_API, params={"limit": 1}, timeout=10)
            r.raise_for_status()
            data = r.json()["data"][0]
            return {
                "value": int(data["value"]),
                "classification": data["value_classification"],
                "timestamp": data["timestamp"],
            }
        except Exception as e:
            print(f"[Sentiment] Fear & Greed failed: {e}")
            return {"value": 50, "classification": "Neutral", "timestamp": None}

    # ------------------------------------------------------------------
    # 2. Latest news
    # ------------------------------------------------------------------
    def fetch_news(self, limit: int = 10) -> list:
        """
        Fetch latest crypto news from CryptoCompare.
        Free tier: 100,000 requests/month. No API key required for basic calls.
        """
        url = f"{CRYPTOCOMPARE_API}/v2/news/"
        params = {
            "lang": "EN",
            "limit": limit,
            "excludeCategories": "Sponsored",
            "api_key": CRYPTOCOMPARE_API_KEY,
        }
        try:
            r = requests.get(url, params=params, timeout=10)
            r.raise_for_status()
            articles = r.json().get("Data", [])
            return [
                {
                    "title": a.get("title", ""),
                    "source": a.get("source_info", {}).get("name", "Unknown"),
                    "published": a.get("published_on", 0),
                    "categories": a.get("categories", ""),
                }
                for a in articles
            ]
        except Exception as e:
            print(f"[Sentiment] News fetch failed: {e}")
            return []

    # ------------------------------------------------------------------
    # 3. Simple keyword sentiment on headlines
    # ------------------------------------------------------------------
    def score_headlines(self, articles: list) -> dict:
        """
        Lightweight keyword-based sentiment scoring on headlines.
        No AI model needed, no API cost.
        """
        bullish_words = [
            "surge", "rally", "bull", "soar", "breakout", "adopt",
            "approve", "etf", "inflow", "record", "high", "gain",
            "partnership", "launch", "upgrade",
        ]
        bearish_words = [
            "crash", "dump", "bear", "plunge", "hack", "ban",
            "lawsuit", "sec", "outflow", "low", "loss", "fear",
            "liquidation", "scam", "fraud", "delay",
        ]

        bull_hits = 0
        bear_hits = 0

        for a in articles:
            title = a["title"].lower()
            for w in bullish_words:
                if w in title:
                    bull_hits += 1
            for w in bearish_words:
                if w in title:
                    bear_hits += 1

        if bull_hits > bear_hits + 1:
            news_bias = "BULLISH"
        elif bear_hits > bull_hits + 1:
            news_bias = "BEARISH"
        else:
            news_bias = "NEUTRAL"

        return {
            "bull_hits": bull_hits,
            "bear_hits": bear_hits,
            "news_bias": news_bias,
        }

    # ------------------------------------------------------------------
    # 4. Combined sentiment
    # ------------------------------------------------------------------
    def analyze(self) -> dict:
        """
        Combine Fear & Greed + news sentiment into a single directional view.
        """
        fg = self.fetch_fear_greed()
        news = self.fetch_news(limit=15)
        news_score = self.score_headlines(news)

        score = 0
        reasons = []

        # Fear & Greed logic (contrarian)
        fg_value = fg["value"]
        if fg_value <= 25:
            score += 2
            reasons.append(f"Extreme Fear ({fg_value}) — contrarian buy zone")
        elif fg_value <= 45:
            score += 1
            reasons.append(f"Fear ({fg_value}) — mild bullish bias")
        elif fg_value >= 75:
            score -= 2
            reasons.append(f"Extreme Greed ({fg_value}) — contrarian sell zone")
        elif fg_value >= 55:
            score -= 1
            reasons.append(f"Greed ({fg_value}) — mild bearish bias")
        else:
            reasons.append(f"Neutral Fear & Greed ({fg_value})")

        # News logic
        if news_score["news_bias"] == "BULLISH":
            score += 1
            reasons.append(
                f"News bullish ({news_score['bull_hits']} bull vs "
                f"{news_score['bear_hits']} bear)"
            )
        elif news_score["news_bias"] == "BEARISH":
            score -= 1
            reasons.append(
                f"News bearish ({news_score['bear_hits']} bear vs "
                f"{news_score['bull_hits']} bull)"
            )
        else:
            reasons.append("News neutral")

        if score >= 1:
            bias = "BULLISH"
        elif score <= -1:
            bias = "BEARISH"
        else:
            bias = "NEUTRAL"

        return {
            "fear_greed": fg,
            "news_count": len(news),
            "news_headlines": news[:5],
            "news_score": news_score,
            "sentiment_bias": bias,
            "sentiment_score": score,
            "reasons": reasons,
        }


if __name__ == "__main__":
    agent = SentimentAgent()
    result = agent.analyze()

    print("\n=== Sentiment Analysis ===")
    print(f"Fear & Greed: {result['fear_greed']['value']} "
          f"({result['fear_greed']['classification']})")
    print(f"News analyzed: {result['news_count']}")
    print(f"News bias: {result['news_score']['news_bias']}")
    print(f"\nOverall sentiment: {result['sentiment_bias']} "
          f"(score {result['sentiment_score']})")
    print("Reasons:")
    for r in result["reasons"]:
        print(f"  - {r}")
    print("\nTop 5 headlines:")
    for h in result["news_headlines"]:
        print(f"  [{h['source']}] {h['title']}")
