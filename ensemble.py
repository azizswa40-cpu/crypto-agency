"""Ensemble — 5 voting agents + 4 analysts + news blackout + JSON output."""
import json
from datetime import datetime
from pathlib import Path
from strategies import EmaAdxStrategy, MeanReversionStrategy, MomentumStrategy
from strategies.funding_rate import FundingRateStrategy
from strategies.liquidity_sweep import LiquiditySweepStrategy
from filters import (
    detect_regime, is_weekend, is_us_session,
    volatility_percentile, in_news_blackout, next_news_event,
)

VOTES_FILE = Path("logs/votes.json")


def build_voting_agents():
    return [
        {"name": "Momentum Agent", "emoji": "⚡", "strategy": MomentumStrategy(20, 10)},
        {"name": "Trend Agent", "emoji": "📈", "strategy": EmaAdxStrategy(adx_min=22)},
        {"name": "Liquidity Agent", "emoji": "💧", "strategy": LiquiditySweepStrategy(20)},
        {"name": "Funding Agent", "emoji": "💰", "strategy": FundingRateStrategy()},
        {"name": "Mean Rev Agent", "emoji": "🔄", "strategy": MeanReversionStrategy(30, 60)},
    ]


def regime_weights(regime):
    w = {"Momentum Agent": 1.0, "Trend Agent": 1.0, "Liquidity Agent": 1.0,
         "Funding Agent": 1.0, "Mean Rev Agent": 1.0}
    if regime == "trending":
        w["Momentum Agent"] = 1.5
        w["Trend Agent"] = 1.5
        w["Mean Rev Agent"] = 0.3
    elif regime == "ranging":
        w["Momentum Agent"] = 0.3
        w["Trend Agent"] = 0.3
        w["Liquidity Agent"] = 1.5
        w["Mean Rev Agent"] = 1.5
    return w


def run_analysts(df):
    out = {}
    try:
        from agents.sentiment import SentimentAgent
        s = SentimentAgent().analyze()
        out["Sentiment Analyst"] = {
            "bias": s["sentiment_bias"], "score": s["sentiment_score"],
            "detail": f"F&G {s['fear_greed']['value']}",
        }
    except Exception:
        out["Sentiment Analyst"] = {"bias": "NEUTRAL", "score": 0, "detail": "err"}
    try:
        from agents.technical_analysis import TechnicalAnalysisAgent
        t = TechnicalAnalysisAgent(df).analyze()
        out["Technical Analyst"] = {
            "bias": t["bias"], "score": t["bias_score"],
            "detail": f"RSI {t['rsi']:.0f}",
        }
    except Exception:
        out["Technical Analyst"] = {"bias": "NEUTRAL", "score": 0, "detail": "err"}
    try:
        from agents.onchain import OnChainAgent
        o = OnChainAgent("BTCUSDT").analyze()
        out["OnChain Analyst"] = {
            "bias": o["bias"], "score": o["score"],
            "detail": f"Fund {o['funding_rate']*100:.4f}%",
        }
    except Exception:
        out["OnChain Analyst"] = {"bias": "NEUTRAL", "score": 0, "detail": "err"}
    try:
        from agents.fundamental import FundamentalAgent
        f = FundamentalAgent().analyze()
        out["Fundamental Analyst"] = {
            "bias": f["bias"], "score": f["score"],
            "detail": f"BTC.D {f.get('btc_dominance', 0):.1f}%",
        }
    except Exception:
        out["Fundamental Analyst"] = {"bias": "NEUTRAL", "score": 0, "detail": "err"}
    return out


def vote(df, symbol="BTCUSDT", write_json=True):
    regime = detect_regime(df)
    weights = regime_weights(regime)
    vol_pct = volatility_percentile(df)
    weekend = is_weekend()
    blackout = in_news_blackout()
    next_event = next_news_event()

    agents = build_voting_agents()
    votes = []
    buy_w = sell_w = 0.0

    for a in agents:
        try:
            d = a["strategy"].prepare(df)
            sig = a["strategy"].generate_signal(d, len(d) - 1)
        except Exception as e:
            sig = {"action": "HOLD", "atr": None, "reason": f"err: {str(e)[:40]}"}
        w = weights.get(a["name"], 1.0)
        action = sig.get("action", "HOLD")
        votes.append({
            "name": a["name"], "emoji": a["emoji"],
            "action": action, "weight": w,
            "reason": sig.get("reason", ""),
            "atr": sig.get("atr"),
        })
        if action == "BUY":
            buy_w += w
        elif action == "EXIT":
            sell_w += w

    total = sum(weights.values())
    buy_pct = buy_w / total * 100
    sell_pct = sell_w / total * 100

    if buy_pct >= 40 and buy_pct > sell_pct:
        decision = "BUY"
    elif sell_pct >= 40:
        decision = "EXIT"
    else:
        decision = "HOLD"

    filters = []
    if blackout:
        filters.append("news_blackout")
        decision = "HOLD"
    if weekend and decision == "BUY":
        filters.append("weekend")
        decision = "HOLD"
    if vol_pct > 95:
        filters.append("vol_extreme")
        decision = "HOLD"

    atr = next((v["atr"] for v in votes if v["atr"] and v["atr"] == v["atr"] and v["atr"] > 0), None)
    analysts = run_analysts(df)

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "symbol": symbol,
        "price": float(df.iloc[-1]["close"]),
        "decision": decision,
        "buy_pct": round(buy_pct, 1),
        "sell_pct": round(sell_pct, 1),
        "buy_count": sum(1 for v in votes if v["action"] == "BUY"),
        "sell_count": sum(1 for v in votes if v["action"] == "EXIT"),
        "regime": regime,
        "vol_pct": round(vol_pct, 1),
        "weekend": weekend,
        "us_session": is_us_session(),
        "blackout": blackout,
        "next_event": next_event.isoformat() if next_event else None,
        "atr": atr,
        "votes": votes,
        "analysts": analysts,
        "filters": filters,
    }

    if write_json:
        try:
            VOTES_FILE.parent.mkdir(exist_ok=True)
            VOTES_FILE.write_text(
                json.dumps(result, indent=2, default=str), encoding="utf-8"
            )
        except Exception as e:
            print(f"[ensemble] JSON write failed: {e}")

    return result
