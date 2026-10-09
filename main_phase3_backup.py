"""
Main runner — Phase 3
Pipeline: data → TA → sentiment → orchestrator → risk → execute (OKX demo) → report
"""

from agents.market_data import MarketDataAgent
from agents.technical_analysis import TechnicalAnalysisAgent
from agents.sentiment import SentimentAgent
from agents.orchestrator import OrchestratorAgent
from agents.risk_manager import RiskManagerAgent
from agents.execution import ExecutionAgent
from agents.audit import AuditAgent
from agents.reporter import ReporterAgent
from config import SYMBOLS, INTERVAL


DRY_RUN = True   # True = simulate, False = send real orders to OKX demo


def run():
    print("\n" + "=" * 60)
    print(f"  CRYPTO AGENCY — Phase 3 ({INTERVAL})  dry_run={DRY_RUN}")
    print("=" * 60)

    audit = AuditAgent()
    rm = RiskManagerAgent(audit)
    execu = ExecutionAgent(audit)
    reporter = ReporterAgent()

    # Balance
    bal = execu.get_balance()
    if bal.get("ok"):
        print(f"\n[Execution] OKX demo USDT balance: {bal['usdt_balance']:.2f}")
    else:
        print(f"\n[Execution] Balance check failed: {bal.get('error')}")

    # Sentiment (market-wide, one call)
    print("\n[Sentiment] Fetching market-wide sentiment...")
    sent_result = SentimentAgent().analyze()
    print(f"  Fear & Greed: {sent_result['fear_greed']['value']} "
          f"({sent_result['fear_greed']['classification']})")
    print(f"  News bias: {sent_result['news_score']['news_bias']}")
    print(f"  Overall: {sent_result['sentiment_bias']}")

    orch = OrchestratorAgent()

    for symbol in SYMBOLS:
        print(f"\n[{symbol}] Running analysis...")

        df = MarketDataAgent(symbol, interval=INTERVAL).fetch_candles()
        if df.empty:
            print(f"[{symbol}] No data. Skipping.")
            continue

        ta_result = TechnicalAnalysisAgent(df).analyze()
        decision = orch.decide(symbol, ta_result, sent_result)

        print(f"  Price:      ${decision['price']:,.2f}")
        print(f"  TA:         {decision['ta_bias']}")
        print(f"  Sentiment:  {decision['sentiment_bias']}")
        print(f"  Decision:   {decision['decision']} "
              f"(confidence {decision['confidence']}%)")

        approved, reason = rm.veto_check(decision)
        audit.log_decision(
            symbol, decision["decision"], decision["confidence"],
            decision["ta_bias"], decision["sentiment_bias"],
            approved, reason, decision["price"],
        )

        if not approved:
            print(f"  X Risk veto: {reason}")
            reporter.send_decision(decision, approved=False, reason=reason)
            continue

        print(f"  OK Risk approved")
        reporter.send_decision(decision, approved=True, reason="approved")

        plan = rm.build_trade_plan(decision)
        print(f"  Plan: {plan['side']} {plan['qty']} {plan['symbol']} "
              f"@ ~{plan['entry']:.2f} | SL {plan['stop_loss']} | "
              f"TP {plan['take_profit']}")

        result = execu.place_order(plan, dry_run=DRY_RUN)
        reporter.send_trade_plan(plan, result)

        if result.get("dry_run") or result.get("code") == "0":
            print(f"  OK Order sent")
        else:
            print(f"  X Order failed: {result}")

    print("\n" + "=" * 60)
    print(f"  Phase 3 complete. dry_run={DRY_RUN}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run()
