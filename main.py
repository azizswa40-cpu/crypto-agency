"""Main runner — MODE SÉCURISÉ. Signal-only par défaut, aucune exécution auto."""
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
    SIGNAL_ONLY_MODE, MAX_DAILY_TRADES, COOLDOWN_HOURS,
    MAX_OPEN_POSITIONS, MAX_DAILY_LOSS_PCT,
)


def check_safety_limits(audit, execu):
    """Check all safety limits. Returns (allowed, reason)."""
    # 1. Kill switch
    if kill_switch.is_active():
        return False, "KILL SWITCH active"

    # 2. Max open positions total
    try:
        positions = execu._all_positions()
        active = [p for p in positions if float(p.get("total", 0)) != 0]
        if len(active) >= MAX_OPEN_POSITIONS:
            return False, f"Max {MAX_OPEN_POSITIONS} positions atteint ({len(active)})"
    except Exception as e:
        return False, f"Impossible de lire positions: {e}"

    # 3. Max daily trades
    today = datetime.utcnow().date().isoformat()
    conn = sqlite3.connect(AUDIT_DB)
    try:
        count = conn.execute(
            "SELECT COUNT(*) FROM orders WHERE ts LIKE ? AND status='New'",
            (f"{today}%",)
        ).fetchone()[0]
    except Exception:
        count = 0
    conn.close()
    if count >= MAX_DAILY_TRADES:
        return False, f"Max {MAX_DAILY_TRADES} trades/jour atteint"

    # 4. Cooldown après dernier trade
    conn = sqlite3.connect(AUDIT_DB)
    try:
        last = conn.execute(
            "SELECT ts FROM orders ORDER BY ts DESC LIMIT 1"
        ).fetchone()
    except Exception:
        last = None
    conn.close()
    if last:
        try:
            last_dt = datetime.fromisoformat(last[0])
            elapsed = datetime.utcnow() - last_dt
            if elapsed < timedelta(hours=COOLDOWN_HOURS):
                remaining = timedelta(hours=COOLDOWN_HOURS) - elapsed
                return False, f"Cooldown: {remaining.seconds//3600}h{remaining.seconds//60%60}m restantes"
        except Exception:
            pass

    return True, "OK"


def run():
    print("=" * 60)
    print(f"  CRYPTO AGENCY — {datetime.utcnow().strftime('%Y-%m-%d %H:%M')} UTC")
    print(f"  dry_run={DRY_RUN}  signal_only={SIGNAL_ONLY_MODE}")
    print("=" * 60)

    audit = AuditAgent()
    execu = ExecutionAgent(audit)
    reporter = ReporterAgent()

    if kill_switch.is_active():
        print("[KILL SWITCH] Active — abort.")
        return

    # Balance
    bal = execu.get_balance()
    if bal.get("ok"):
        print(f"\n[Bitget] Balance: {bal['usdt_balance']:.4f} USDT")

    # Safety check
    allowed, reason = check_safety_limits(audit, execu)
    print(f"\n[Safety] {reason}")

    # Scan symbols
    for symbol in STRATEGY_SYMBOLS:
        print(f"\n[{symbol}] Scanning...")

        if execu.has_open_position(symbol):
            print(f"  Position déjà ouverte — skip")
            continue

        df = MarketDataAgent(symbol, interval=STRATEGY_INTERVAL).fetch_candles()
        if df.empty:
            print(f"  Pas de données")
            continue
        df = df.tail(CANDLE_LIMIT)

        sig = evaluate(df, ema_fast=EMA_FAST, ema_slow=EMA_SLOW, adx_min=ADX_MIN)
        if not sig:
            print(f"  Données insuffisantes")
            continue

        print(f"  Prix: ${sig['price']:,.2f}")
        print(f"  Signal: {sig['signal']} — {sig['reason']}")

        if sig["signal"] != "BUY":
            audit.log_decision(symbol, "HOLD", 0,
                               "BULLISH" if sig["trend_up"] else "BEARISH",
                               "N/A", False, sig["reason"], sig["price"])
            continue

        # Signal détecté — on log et on ALERTE (mais pas d'exécution en signal-only)
        print(f"  ✅ Signal BUY détecté")

        entry = sig["price"]
        atr = sig["atr"]
        sl = entry - 2.0 * atr
        tp = entry + 6.0 * atr

        audit.log_signal(symbol, "BUY", 90, 1, entry, sl, tp, 3.0, sig["reason"])

        # Telegram ALERT
        reporter._send(
            f"🟢 *SIGNAL DÉTECTÉ — {symbol}*\n\n"
            f"💰 Prix: `${entry:,.2f}`\n"
            f"🛑 SL: `${sl:,.2f}` (-2×ATR)\n"
            f"🎯 TP: `${tp:,.2f}` (+6×ATR)\n"
            f"⚖️ R:R `1:3`\n\n"
            f"📊 *{sig['reason']}*\n\n"
            f"⚠️ *Mode signal-only : aucun ordre exécuté*\n"
            f"Pour exécuter, modifier `SIGNAL_ONLY_MODE = False` dans config.py"
        )

        if not allowed:
            print(f"  ⛔ Safety bloque: {reason}")
            continue

        if SIGNAL_ONLY_MODE:
            print(f"  📢 Signal envoyé (SIGNAL_ONLY_MODE actif)")
            continue

        # Exécution réelle (uniquement si SIGNAL_ONLY_MODE = False)
        print(f"  ⚠️ Exécution autorisée...")
        decision = {
            "symbol": symbol, "decision": "BUY", "confidence": 90,
            "ta_bias": "BULLISH", "sentiment_bias": "N/A",
            "price": entry, "atr": atr, "reasons": [sig["reason"]],
        }
        rm = RiskManagerAgent(audit)
        approved, reason = rm.veto_check(decision)
        audit.log_decision(symbol, "BUY", 90, "BULLISH", "N/A", approved, reason, entry)

        if not approved:
            print(f"  Risk veto: {reason}")
            continue

        plan = rm.build_trade_plan(decision)
        result = execu.place_order(plan, dry_run=DRY_RUN)

        if result.get("code") == "00000":
            oid = (result.get("data") or {}).get("orderId", "N/A")
            reporter.send_position_opened(plan, entry, oid,
                                          strategy_name="Momentum Breakout",
                                          reason=sig["reason"])
            print(f"  ✅ Ordre envoyé: {oid}")

    print("\n" + "=" * 60)
    print(f"  Terminé.")
    print("=" * 60)


if __name__ == "__main__":
    run()
