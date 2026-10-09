"""Main runner — Bitget Demo with kill switch."""
from datetime import datetime, timedelta
import sqlite3
from agents.market_data import MarketDataAgent
from agents.audit import AuditAgent
from agents.risk_manager import RiskManagerAgent
from agents.execution import ExecutionAgent
from agents.reporter import ReporterAgent
from agents import kill_switch
from strategy import evaluate
from config import (
    STRATEGY_SYMBOLS, STRATEGY_INTERVAL, CANDLE_LIMIT,
    EMA_FAST, EMA_SLOW, ADX_MIN, DRY_RUN, AUDIT_DB,
)


def run():
    print("\n" + "=" * 60)
    print(f"  CRYPTO AGENCY — Bitget Demo  dry_run={DRY_RUN}")
    print("=" * 60)

    audit = AuditAgent()
    execu = ExecutionAgent(audit)
    reporter = ReporterAgent()

    # Kill switch check
    if kill_switch.is_active():
        print("\n🚨 [KILL SWITCH] Active — closing all positions and halting.")
        result = execu.close_all()
        reporter._send(f"🚨 *KILL SWITCH ACTIVATED*\n\nClosed all positions.\nResult: `{result}`\n\nRemove `logs/KILL` file to resume.")
        return

    rm = RiskManagerAgent(audit)

    bal = execu.get_balance()
    if bal.get("ok"):
        print(f"\n[Bitget] Demo USDT balance: {bal['usdt_balance']:.2f}")

    for symbol in STRATEGY_SYMBOLS:
        print(f"\n{'='*60}")
        print(f"  [{symbol}] Daily scan")
        print(f"{'='*60}")

        if execu.has_open_position(symbol):
            print(f"  Already in position on {symbol}. Skipping.")
            continue

        df = MarketDataAgent(symbol, interval=STRATEGY_INTERVAL).fetch_candles()
        if df.empty:
            print(f"  No data.")
            continue
        df = df.tail(CANDLE_LIMIT)

        sig = evaluate(df, ema_fast=EMA_FAST, ema_slow=EMA_SLOW, adx_min=ADX_MIN)
        if not sig:
            print(f"  Insufficient data.")
            continue

        print(f"  Price: ${sig['price']:,.2f}")
        print(f"  EMA{EMA_FAST}: ${sig['ema_fast']:,.2f} | EMA{EMA_SLOW}: ${sig['ema_slow']:,.2f}")
        print(f"  ADX: {sig['adx']:.1f} | ATR: ${sig['atr']:.2f}")
        print(f"  Signal: {sig['signal']} — {sig['reason']}")

        if sig["signal"] != "BUY":
            audit.log_decision(symbol, "HOLD", 0,
                               "BULLISH" if sig["trend_up"] else "BEARISH",
                               "N/A", False, sig["reason"], sig["price"])
            print(f"  No trade.")
            continue

        decision = {
            "symbol": symbol, "decision": "BUY", "confidence": 90,
            "ta_bias": "BULLISH", "sentiment_bias": "N/A",
            "price": sig["price"], "atr": sig["atr"], "reasons": [sig["reason"]],
        }

        approved, reason = rm.veto_check(decision)
        audit.log_decision(symbol, "BUY", 90, "BULLISH", "N/A", approved, reason, sig["price"])

        if not approved:
            print(f"  X Risk veto: {reason}")
            reporter.send_decision(decision, approved=False, reason=reason)
            continue

        print(f"  OK Risk approved")
        plan = rm.build_trade_plan(decision)
        risk_d = abs(plan["entry"] - plan["stop_loss"])
        reward_d = abs(plan["take_profit"] - plan["entry"])
        rr = reward_d / risk_d if risk_d > 0 else 0

        audit.log_signal(symbol, "BUY", 90, 1, plan["entry"], plan["stop_loss"],
                         plan["take_profit"], rr, sig["reason"])

        reporter.send_professional_signal(
            symbol=symbol, direction="BUY", confidence=90,
            entry=plan["entry"], atr=plan["atr"],
            analysts={"technical": f"BULLISH (EMA{EMA_FAST}/{EMA_SLOW})",
                      "adx": f"{sig['adx']:.1f}",
                      "atr": f"${sig['atr']:.2f}",
                      "signal": sig["reason"]},
            ceo_reasoning=sig["reason"])

        print(f"  Plan: {plan['side']} {plan['qty']} {plan['symbol']} @ ${plan['entry']:.2f}")
        print(f"  SL: ${plan['stop_loss']:.2f} | TP: ${plan['take_profit']:.2f} | RR 1:{rr:.1f}")

        result = execu.place_order(plan, dry_run=DRY_RUN)
        if DRY_RUN:
            print(f"  OK DRY RUN")
        elif result.get("code") == "00000":
            oid = (result.get("data") or {}).get("orderId", "N/A")
            reporter.send_position_opened(plan, plan["entry"], oid)
            print(f"  OK Order sent: {oid}")
        else:
            print(f"  X Order failed: {result}")

    print("\n" + "=" * 60)
    print(f"  Complete. dry_run={DRY_RUN}")
    print("=" * 60 + "\n")


if __name__ == "__main__":
    run()
