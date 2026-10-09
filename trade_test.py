"""
Force a real BUY on Bitget Demo to validate the full pipeline.
Bypasses the Momentum breakout condition (which is rare).
"""
from agents.market_data import MarketDataAgent
from agents.audit import AuditAgent
from agents.execution import ExecutionAgent
from agents.reporter import ReporterAgent
from agents.risk_manager import RiskManagerAgent
from strategy import compute_indicators
from config import EMA_FAST, EMA_SLOW, ADX_MIN

audit = AuditAgent()
execu = ExecutionAgent(audit)
reporter = ReporterAgent()
rm = RiskManagerAgent(audit)


def cleanup():
    """Close any open positions and clean stale DB entries."""
    print("=== 1. Nettoyage ===")
    pos = execu._all_positions()
    print(f"Positions ouvertes avant: {len(pos)}")
    if pos:
        print("Fermeture:", execu.close_all())
    import sqlite3
    from config import AUDIT_DB
    from datetime import datetime
    conn = sqlite3.connect(AUDIT_DB)
    n1 = conn.execute("SELECT COUNT(*) FROM signals WHERE outcome='open'").fetchone()[0]
    n2 = conn.execute("SELECT COUNT(*) FROM orders WHERE status='New'").fetchone()[0]
    conn.execute("UPDATE signals SET outcome='closed', closed_at=? WHERE outcome='open'",
                 (datetime.utcnow().isoformat(),))
    conn.execute("UPDATE orders SET status='cancelled' WHERE status='New'")
    conn.commit()
    conn.close()
    print(f"Nettoyage: {n1} signaux, {n2} ordres")
    print()


def get_market_data():
    print("=== 2. Donnees marche BTCUSDT ===")
    df = MarketDataAgent("BTCUSDT", interval="1D").fetch_candles()
    if df.empty:
        print("ERREUR: pas de donnees")
        return None
    d = compute_indicators(df, ema_fast=EMA_FAST, ema_slow=EMA_SLOW).dropna()
    last = d.iloc[-1]
    info = {
        "price": float(last["close"]),
        "ema_fast": float(last["ema_fast"]),
        "ema_slow": float(last["ema_slow"]),
        "adx": float(last["adx"]),
        "atr": float(last["atr"]),
        "trend_up": bool(last["ema_fast"] > last["ema_slow"]),
    }
    print(f"Price:     ${info['price']:,.2f}")
    print(f"EMA50:     ${info['ema_fast']:,.2f}")
    print(f"EMA200:    ${info['ema_slow']:,.2f}")
    print(f"ADX:       {info['adx']:.1f}")
    print(f"ATR:       ${info['atr']:,.2f}")
    print(f"Trend:     {'UP' if info['trend_up'] else 'DOWN'}")
    print()
    return info


def place_test_trade(info):
    print("=== 3. Placement du trade test ===")

    if not info["trend_up"]:
        print("Pas en uptrend -> on force quand meme pour tester")
        print()

    decision = {
        "symbol": "BTCUSDT",
        "decision": "BUY",
        "confidence": 90,
        "ta_bias": "BULLISH",
        "sentiment_bias": "N/A",
        "price": info["price"],
        "atr": info["atr"],
        "reasons": ["FORCED TEST TRADE"],
    }

    approved, reason = rm.veto_check(decision)
    print(f"Risk check: {approved} - {reason}")

    if not approved:
        print("Risk veto -> trade annule")
        return None

    plan = rm.build_trade_plan(decision)
    print()
    print(f"Plan: BUY 1 contrat BTCUSDT")
    print(f"Entry: ${plan['entry']:,.2f}")
    print(f"SL:    ${plan['stop_loss']:,.2f}")
    print(f"TP:    ${plan['take_profit']:,.2f}")
    print(f"Risk:  ${plan['risk_usdt']:.2f}")
    print()

    print("Envoi a Bitget...")
    result = execu.place_order(plan, dry_run=False)
    print(f"Code: {result.get('code')} | Msg: {result.get('msg')}")

    if result.get("code") == "00000":
        oid = (result.get("data") or {}).get("orderId", "N/A")
        print(f"ORDER ID: {oid}")

        audit.log_signal("BTCUSDT", "BUY", 90, 1,
                         plan["entry"], plan["stop_loss"], plan["take_profit"],
                         3.0, "FORCED TEST TRADE")

        reporter.send_position_opened(plan, plan["entry"], oid)
        print("Telegram alerte envoyee")
        return oid
    else:
        print(f"ERREUR COMPLETE: {result}")
        return None


def main():
    print("=" * 60)
    print("  TEST TRADE - Bitget Demo")
    print("=" * 60)
    print()

    cleanup()
    info = get_market_data()
    if not info:
        return

    oid = place_test_trade(info)

    print()
    print("=" * 60)
    if oid:
        print(f"  SUCCES - Order {oid}")
        print(f"  Verifie sur Bitget:")
        print(f"  https://www.bitget.com/fr/futures/usdt/BTCUSDT")
        print(f"  Onglet: Positions")
    else:
        print("  ECHEC")
    print("=" * 60)


if __name__ == "__main__":
    main()
