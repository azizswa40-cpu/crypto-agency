"""
Orchestrator Agent
Combines Technical Analysis bias + Sentiment bias into a single decision.

Decision rules:
  - Both BULLISH          → BUY signal
  - Both BEARISH          → SELL signal
  - TA BULLISH, Sent NEUTRAL  → WEAK BUY
  - TA BEARISH, Sent NEUTRAL  → WEAK SELL
  - Any conflict          → HOLD
"""


class OrchestratorAgent:
    def __init__(self):
        pass

    def decide(self, symbol: str, ta_result: dict, sent_result: dict) -> dict:
        ta_bias = ta_result["bias"]
        sent_bias = sent_result["sentiment_bias"]

        reasons = []
        decision = "HOLD"
        confidence = 0

        # Both agree — strongest signals
        if ta_bias == "BULLISH" and sent_bias == "BULLISH":
            decision = "BUY"
            confidence = 85
            reasons.append("Technical and sentiment both bullish")

        elif ta_bias == "BEARISH" and sent_bias == "BEARISH":
            decision = "SELL"
            confidence = 85
            reasons.append("Technical and sentiment both bearish")

        # TA signal with neutral sentiment — weaker but valid
        elif ta_bias == "BULLISH" and sent_bias == "NEUTRAL":
            decision = "WEAK BUY"
            confidence = 55
            reasons.append("Technical bullish, sentiment neutral")

        elif ta_bias == "BEARISH" and sent_bias == "NEUTRAL":
            decision = "WEAK SELL"
            confidence = 55
            reasons.append("Technical bearish, sentiment neutral")

        # Sentiment signal with neutral TA — contrarian play
        elif ta_bias == "NEUTRAL" and sent_bias == "BULLISH":
            decision = "WEAK BUY"
            confidence = 50
            reasons.append("Sentiment bullish, technical neutral (contrarian)")

        elif ta_bias == "NEUTRAL" and sent_bias == "BEARISH":
            decision = "WEAK SELL"
            confidence = 50
            reasons.append("Sentiment bearish, technical neutral (contrarian)")

        # Conflict — no trade
        else:
            decision = "HOLD"
            confidence = 0
            reasons.append(f"Conflict: TA={ta_bias}, Sentiment={sent_bias}")

        # Confidence adjustment based on TA score strength
        ta_strength = abs(ta_result.get("bias_score", 0))
        confidence = min(95, confidence + (ta_strength * 3))

        return {
            "symbol": symbol,
            "decision": decision,
            "confidence": confidence,
            "ta_bias": ta_bias,
            "sentiment_bias": sent_bias,
            "price": ta_result["price"],
            "atr": ta_result["atr"],
            "reasons": reasons,
        }
