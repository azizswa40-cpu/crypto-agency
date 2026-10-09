"""
Quick trade test — open, wait 5 minutes, close, send Telegram P&L.
Validates the FULL lifecycle: entry → hold → close → P&L alert.
"""
import time
import sqlite3
from datetime import datetime
from agents.market_data import MarketDataAgent
from agents.audit import AuditAgent
from agents.execution import ExecutionAgent
from agents.reporter import ReporterAgent
from agents.risk_manager import RiskManagerAgent
from strategy import compute_indicators
from config import EMA_FAST, EMA_SLOW, AUDIT_DB

WAIT_SECONDS = 300  # 5 minutes

audit = AuditAgent()
execu = ExecutionAgent(audit)
reporter = ReporterAgent()
rm = RiskManagerAgent(audit)


def cleanup():
    print("=== 1. Nettoyage ===")
    pos = execu._all_positions()
    print(f"Positions ouvertes avant: {len(pos)}")
    if pos:
        print("Fermeture:", execu.close_all())
    conn = sqlite3.connect(AUDIT_DB)
    conn.execute("UPDATE signals SET outcome='closed', closed_at=? WHERE outcome='open'",
                 (datetime.utcnow().isoformat(),))
    conn.execute("UPDATE orders SET status='cancelled' WHERE status='New'")
    conn.commit()
    conn.close()
    print("DB nettoyee")
    print()


def open_position():
    print("=== 2. Ouverture de la position ===")
    df = MarketDataAgent("BTCUSDT", interval="1D").fetch_candles()
    d = compute_indicators(df, ema_fast=EMA_FAST, ema_slow=EMA_SLOW).dropna()
    last = d.iloc[-1]

    price = float(last["close"])
    atr = float(last["atr"])
    print(f"BTC price: ${price:,.2f}")
    print(f"ATR: ${atr:,.2f}")
    print()

    decision = {
        "symbol": "BTCUSDT", "decision": "BUY", "confidence": 90,
        "ta_bias": "BULLISH", "sentiment_bias": "N/A",
        "price": price, "atr": atr, "reasons": ["5min test"],
    }

    approved, reason = rm.veto_check(decision)
    print(f"Risk check: {approved} - {reason}")
    if not approved:
        return None, None

    plan = rm.build_trade_plan(decision)
    print(f"Entry: ${plan['entry']:,.2f}")
    print(f"SL:    ${plan['stop_loss']:,.2f}")
    print(f"TP:    ${plan['take_profit']:,.2f}")
    print()

    print("Envoi ordre a Bitget...")
    result = execu.place_order(plan, dry_run=False)
    print(f"Code: {result.get('code')} | Msg: {result.get('msg')}")

    if result.get("code") != "00000":
        print(f"ECHEC: {result}")
        return None, None

    oid = (result.get("data") or {}).get("orderId", "N/A")
    print(f"ORDER ID: {oid}")
    print()

    # Log signal
    audit.log_signal("BTCUSDT", "BUY", 90, 1,
                     plan["entry"], plan["stop_loss"], plan["take_profit"],
                     3.0, "5min test trade")

    # Envoi alerte Telegram avec infos enrichies
    reporter.send_position_opened(plan, plan["entry"], oid,
                                  strategy_name="Momentum Breakout (test 5min)",
                                  reason="Test cycle complet open->close")
    print("Telegram: POSITION OPENED envoye")
    print()

    return plan, oid


def wait_and_close(plan, oid):
    print(f"=== 3. Attente {WAIT_SECONDS}s ({WAIT_SECONDS//60} min) ===")
    for remaining in range(WAIT_SECONDS, 0, -30):
        print(f"  Temps restant: {remaining}s...")
        time.sleep(30)

    print()
    print("=== 4. Recuperation du P&L actuel ===")
    positions = execu._all_positions()
    active = [p for p in positions if float(p.get("total", 0)) != 0]

    if not active:
        print("Position deja fermee (SL ou TP touche)")
        current_price = plan["entry"]
        pnl_pct = 0
    else:
        p = active[0]
        current_price = float(p.get("markPrice", plan["entry"]))
        entry = float(p.get("openPriceAvg", plan["entry"]))
        pnl_pct = (current_price - entry) / entry * 100
        print(f"Prix actuel: ${current_price:,.2f}")
        print(f"Prix d'entree: ${entry:,.2f}")
        print(f"P&L non realise: {pnl_pct:+.2f}%")
        print()

    print("=== 5. Fermeture de la position ===")
    r = execu.close_position("BTCUSDT")
    print(f"Close: {r.get('code')} | {r.get('msg')}")

    # Update DB
    conn = sqlite3.connect(AUDIT_DB)
    conn.execute("UPDATE signals SET outcome='win', closed_at=?, pnl_pct=? WHERE outcome='open'",
                 (datetime.utcnow().isoformat(), pnl_pct))
    conn.commit()
    conn.close()

    return current_price, pnl_pct


def send_close_alert(plan, oid, exit_price, pnl_pct):
    entry = plan["entry"]
    pnl_usdt = (exit_price - entry) * 0.0001  # 1 contrat = 0.0001 BTC

    emoji = "✅" if pnl_pct > 0 else "❌"
    text = (
        f"{emoji} *POSITION CLOSED*\n"
        f"━━━━━━━━━━━━━━━━━━━━━\n\n"
        f"📊 *Stratégie:* Momentum Breakout (test 5min)\n"
        f"🕐 *Durée:* 5 minutes\n\n"
        f"💼 *Trade:*\n"
        f"• Symbol: *BTCUSDT*\n"
        f"• Direction: *LONG*\n"
        f"• Contrats: `1`\n\n"
        f"📥 *Entry:* `${entry:,.2f}`\n"
        f"📤 *Exit:* `${exit_price:,.2f}`\n\n"
        f"💰 *P&L:*\n"
        f"• Pourcentage: `{pnl_pct:+.4f}%`\n"
        f"• USDT: `${pnl_usdt:+.4f}`\n\n"
        f"🆔 *Order ID:* `{oid}`\n\n"
        f"⚪ *Outcome:* TEST (position fermee manuellement)"
    )
    reporter._send(text)
    print("Telegram: POSITION CLOSED envoye")


def main():
    print("=" * 60)
    print("  TEST 5 MINUTES - Cycle complet")
    print("=" * 60)
    print()

    cleanup()
    plan, oid = open_position()
    if not plan:
        print("Impossible d'ouvrir la position - arret")
        return

    exit_price, pnl_pct = wait_and_close(plan, oid)
    send_close_alert(plan, oid, exit_price, pnl_pct)

    print()
    print("=" * 60)
    print("  TEST TERMINE")
    print("=" * 60)


if __name__ == "__main__":
    main()
