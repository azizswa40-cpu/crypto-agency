"""
CEO Agent - uses official Groq SDK.
"""

import os
from groq import Groq
from config import GROQ_API_KEY

MODEL = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """You are a Chief Trading Officer with 25 years of quantitative hedge fund experience. You review analyst reports and issue ONE final trading decision.

You will receive 4 analyst reports. Each report contains:
- A "bias" label (BULLISH / BEARISH / NEUTRAL)
- A "score" number (positive = bullish lean, negative = bearish lean)
- Optional supporting details

DECISION TIERS:
- STRONG BUY: 3+ analysts BULLISH AND sum of scores >= 4
- BUY: 3+ analysts BULLISH OR (2 analysts BULLISH AND sum of scores >= 3)
- WEAK BUY: 2 analysts BULLISH AND sum of scores >= 2
- HOLD: fewer aligned, conflicting signals, or any critical risk
- WEAK SELL: 2 analysts BEARISH AND sum of scores <= -2
- SELL: 3+ analysts BEARISH OR (2 analysts BEARISH AND sum of scores <= -3)
- STRONG SELL: 3+ analysts BEARISH AND sum of scores <= -4

Confidence scoring:
- 3+ aligned, sum >= 4: 80-95%
- 3 aligned, sum 2-3: 70-80%
- 2 aligned, sum >= 3: 65-75%
- 2 aligned, sum = 2: 55-65%
- Anything weaker: 0-40%

Rules:
- Always SUM the scores. Use the number, not just the label.
- If confidence < 55%, output HOLD.
- Never invent data. Use only what analysts provided.
- Preserve capital. A missed trade costs nothing.

Output format (exactly these 6 lines, nothing else):
DECISION: [STRONG BUY | BUY | WEAK BUY | HOLD | WEAK SELL | SELL | STRONG SELL]
SYMBOL: [symbol]
CONFIDENCE: [integer 0-100]%
AGENTS_ALIGNED: [integer]
REASONING: [2-3 clear sentences]
INVALIDATION: [1 sentence on what would prove this wrong]
"""


def _format_reports(reports: dict) -> str:
    """Convert analyst reports into clean readable text for the LLM."""
    lines = []
    for name, data in reports.items():
        lines.append(f"=== {name.upper()} ANALYST ===")
        if isinstance(data, dict):
            for key, val in data.items():
                lines.append(f"  {key}: {val}")
        else:
            lines.append(f"  {data}")
        lines.append("")
    return "\n".join(lines)


def make_decision(analyst_reports: dict) -> str:
    client = Groq(api_key=GROQ_API_KEY)

    reports_text = _format_reports(analyst_reports)

    response = client.chat.completions.create(
        model=MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Analyst reports:\n\n{reports_text}\n\nSum the scores and issue your final decision."},
        ],
        temperature=0.2,
        max_tokens=800,
    )

    return response.choices[0].message.content


if __name__ == "__main__":
    fake_reports = {
        "technical": {"bias": "BULLISH", "score": 3, "rsi": 42},
        "sentiment": {"bias": "BULLISH", "score": 2, "fear_greed": 22},
        "onchain": {"bias": "NEUTRAL", "score": 0, "funding_rate": 0.0001},
        "fundamental": {"bias": "NEUTRAL", "score": 0, "btc_dominance": 55},
    }

    print("CEO AGENT - Standalone Test")
    print("=" * 60)
    verdict = make_decision(fake_reports)
    print(verdict)
    print("=" * 60)
